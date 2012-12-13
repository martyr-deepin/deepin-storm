#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 ~ 2012 Deepin, Inc.
#               2011 ~ 2012 Wang Yong
# 
# Author:     Wang Yong <lazycat.manatee@gmail.com>
# Maintainer: Wang Yong <lazycat.manatee@gmail.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import gevent module before any other modules.
from gevent import monkey, Greenlet
from gevent.pool import Pool
from gevent.queue import Queue
monkey.patch_all()

import commands
import subprocess
from events import EventRegister
import threading as td
import urlparse
import time
from http import FetchHttp
from ftp import FetchFtp
import os
from utils import remove_file, create_directory, get_hash, remove_directory

STATUS_WAITING = 0
STATUS_DOWNLOADING = 1
STATUS_FINISH = 2

REALTIME_DELAY = 1              # seconds

class FetchFile(object):
    '''
    class docs
    '''
	
    def __init__(self,
                 file_url,
                 file_save_dir=None,
                 file_save_name=None,
                 file_hash_info=None,
                 concurrent_num=5,
                 buffer_size=8192, # in byte
                 min_split_size=20480, # in byte
                 file_size=None
                 ):
        '''
        init docs
        '''
        self.file_url = file_url
        
        if file_save_dir == None:
            try:
                self.file_save_dir = commands.getoutput("xdg-user-dir DOWNLOAD")
            except:
                self.file_save_dir = "/tmp"
        else:
            self.file_save_dir = file_save_dir
            
        if file_save_name == None:
            self.file_save_name = os.path.split(file_url)[1]
        else:
            self.file_save_name = file_save_name
            
        self.file_save_path = os.path.join(self.file_save_dir, self.file_save_name)    
            
        self.temp_save_dir = os.path.join(self.file_save_dir, "%s_tmp" % self.file_save_name)
        self.temp_save_path = os.path.join(self.temp_save_dir, self.file_save_name)    
        
        self.concurrent_num = concurrent_num
        self.file_hash_info = file_hash_info
        self.buffer_size = buffer_size
        self.min_split_size = min_split_size
        self.fetch = self.get_fetch()
        
        self.update_greenlet_callbacks = []
        
        self.signal = EventRegister()
        
        self.stop_flag = False
        self.pause_flag = False
        
        self.greenlet_dict = {}
        self.pool = Pool(self.concurrent_num)
        
        if file_size:
            self.file_size = file_size
        
    def init_file_size(self):    
        self.file_size = self.fetch.get_file_size()
        
    def get_fetch(self):
        url = urlparse.urlparse(self.file_url)
        if url[0] == "http":
            return FetchHttp(self.file_url)
        elif url[0] == "ftp":
            return FetchFtp(self.file_url)
        
    def get_piece_ranges(self):    
        if self.file_size < self.min_split_size:
            return [(0, self.last_byte_index)]
        else:
            split_num = self.concurrent_num
            if self.file_size < self.min_split_size * split_num:
                split_size = self.min_split_size
            else:
                split_size = self.file_size / split_num
                
            ranges = []
            for index in xrange(split_num - 1):
                ranges.append(((index * split_size), (index + 1) * split_size - 1))
                
            ranges.append(((split_num - 1) * split_size, self.last_byte_index))
            
            return ranges
        
    def start(self):
        if self.file_size > 0:
            self.last_byte_index = self.file_size - 1
            
            create_directory(self.temp_save_dir)
            
            (downloaded_pieces, download_pieces, downloaded_size) = self.get_download_pieces()
            
            if downloaded_size == self.file_size:
                self.signal.emit("no-need-fetch")
            else:
                current_time = time.time()
                self.update_info = {
                    "file_size" : self.file_size,
                    "downloaded_size" : downloaded_size,
                    "start_time" : current_time,
                    "update_time" : current_time,
                    "remain_time" : -1,
                    "average_speed" : -1,
                    "realtime_speed" : -1,
                    "realtime_time" : current_time,
                    "realtime_size" : 0,
                    }
                
                self.signal.emit("start", self.update_info)
                
                for (begin, end) in download_pieces:
                    self.create_greenlet(begin, end)
                    
                [self.pool.start(greenlet) for greenlet in self.greenlet_dict.values()]
                self.pool.join()
                
            if self.stop_flag:
                remove_directory(self.temp_save_dir)
                self.signal.emit("stop")
            elif self.pause_flag:
                self.signal.emit("pause")
            else:
                offset_ids = sorted(map(lambda (start, end): start, downloaded_pieces + download_pieces))
                command = "cat " + ' '.join(map(lambda offset_id: "%s_%s" % (self.temp_save_path, offset_id), offset_ids)) + " > %s" % self.file_save_path
                subprocess.Popen(command, shell=True).wait()
                
                remove_directory(self.temp_save_dir)
                
                if self.file_hash_info != None:
                    (expect_hash_type, expect_hash_value) = self.file_hash_info
                    hash_value = get_hash(self.file_save_path, expect_hash_type)
                    if hash_value != expect_hash_value:
                        self.signal.emit("check-hash-failed", expect_hash_value, hash_value)
                    else:    
                        self.signal.emit("finish")
                else:
                    self.signal.emit("finish")
        else:
            self.signal.emit("get-file-size-failed")
            
    def stop(self, pause_flag=False):
        if pause_flag:
            self.pause_flag = pause_flag
        else:
            self.stop_flag = True
        
        for greenlet in self.greenlet_dict.values():
            if not greenlet.ready():
                greenlet.kill()
            
        self.pool.kill()    
            
    def get_download_pieces(self):
        if os.path.exists(self.temp_save_dir):
            downloaded_size = 0
            downloaded_pieces = []
            for download_file in os.listdir(self.temp_save_dir):
                try:
                    (file_name, file_offset_part) = download_file.rsplit("_", 1)
                    file_offset = int(file_offset_part)
                    if (file_name == self.file_save_name 
                        and 0 <= file_offset <= self.file_size):
                        file_size = os.stat(os.path.join(self.temp_save_dir, download_file)).st_size
                        if file_size > 0:
                            downloaded_size += file_size
                            downloaded_pieces.append((file_offset, file_offset + file_size - 1))
                except:
                    pass
                
            downloaded_pieces = sorted(downloaded_pieces, key=lambda (start, end): start)    
            
            if len(downloaded_pieces) == 0:
                return ([], self.get_piece_ranges(), 0)
            else:
                if self.piece_is_complete(downloaded_pieces):
                    return ([], downloaded_pieces, self.file_size)
                else:
                    need_download_pieces = []
                    download_tag = 0
                    for (piece_index, (start, end)) in enumerate(downloaded_pieces):
                        if start != download_tag:
                            need_download_pieces.append((download_tag + 1, start - 1))
                            
                        download_tag = end
                        
                        if piece_index == len(downloaded_pieces) - 1:
                            if download_tag != self.last_byte_index:
                                need_download_pieces.append((download_tag + 1, self.last_byte_index))
                            
                    return (downloaded_pieces, need_download_pieces, downloaded_size)
        else:
            return ([], self.get_piece_ranges(), 0)
        
    def piece_is_complete(self, pieces):
        if pieces[0][0] != 0:
            return False
        
        if pieces[-1][1] != self.last_byte_index:
            return False
        
        for (index, (start, end)) in enumerate(pieces):
            if index != 0:
                if start != pieces[index - 1][1] + 1:
                    return False
            
        return True
            
    def create_greenlet(self, begin, end):
        greenlet = Greenlet(self.update, (begin, end)) # greenlet
        greenlet.link(self.finish)
        greenlet.info = {
            "id" : begin,
            "status" : STATUS_WAITING,   # status
            "range_size" : end - begin,  # range size
            "remain_size" : end - begin, # remain size
            "start_time" : -1,           # start time
            "update_time" : -1,          # udpate time
            "average_speed" : -1,        # average speed
            "remain_time" : -1,          # remain time
            "realtime_speed" : -1,       # realtime speed
            "realtime_time" : -1,        # realtime time
            "realtime_size" : 0,         # realtime size
            }
        self.greenlet_dict[begin] = greenlet
        
        return greenlet
            
    def finish(self, greenlet):
        # Mark download completed.
        greenlet.info["status"] = STATUS_FINISH
        
    def helper_other_greenlet(self):    
        '''
        I found use below code in function `finish` will make download slower.
        '''
        # Try help other greenlet.
        status_list = map(lambda greenlet: (greenlet.info["status"], greenlet), self.greenlet_dict.values())    
        downloading_infos = filter(lambda (status, greenlet): status == STATUS_DOWNLOADING, status_list)
        waiting_infos = filter(lambda (status, greenlet): status == STATUS_WAITING, status_list)
        
        if len(downloading_infos) > 0 and self.concurrent_num - len(downloading_infos) > len(waiting_infos):
            slowest_greenlet = sorted(downloading_infos, key=lambda (status, greenlet): int(greenlet.info["remain_time"]), reverse=True)[0][1]
            if slowest_greenlet.info["remain_time"] > 5:
                slowest_greenlet.kill()
                
                info = slowest_greenlet.info
                remain_begin = info["id"] + info["range_size"] - info["remain_size"]
                remain_split = remain_begin + int(info["remain_size"] / 2)
                remain_end = remain_begin + info["remain_size"] 
                
                self.pool.start(self.create_greenlet(remain_begin, remain_split))
                self.pool.start(self.create_greenlet(remain_split + 1, remain_end))
        
    def update_greenlet(self, begin, data):
        data_len = len(data)
        greenlet = self.greenlet_dict[begin]
        current_time = time.time()
        remain_size = greenlet.info["remain_size"] - data_len
        average_speed = (greenlet.info["range_size"] - remain_size) / (current_time - greenlet.info["start_time"])
        
        greenlet.info["remain_size"] = remain_size
        greenlet.info["update_time"] = current_time
        greenlet.info["average_speed"] = average_speed
        greenlet.info["remain_time"] = remain_size / average_speed
        greenlet.info["realtime_size"] += data_len
        
        if remain_size == 0 or current_time - greenlet.info["realtime_time"] >= REALTIME_DELAY:
            greenlet.info["realtime_speed"] = greenlet.info["realtime_size"] / (current_time - greenlet.info["realtime_time"])
            greenlet.info["realtime_time"] = current_time
            greenlet.info["realtime_size"] = 0
        
            self.signal.emit("part_update", greenlet.info)
            
    def update(self, (begin, end)):
        current_time = time.time()
        greenlet = self.greenlet_dict[begin]
        greenlet.info["status"] = STATUS_DOWNLOADING
        greenlet.info["range_size"] = end - begin
        greenlet.info["remain_size"] = end - begin
        greenlet.info["start_time"] = current_time
        greenlet.info["update_time"] = current_time
        greenlet.info["realtime_time"] = current_time
        greenlet.info["realtime_size"] = 0
        
        self.signal.emit("part_start", begin, greenlet.info)
        
        filepath = "%s_%s" % (self.temp_save_path, begin)
        
        remove_file(filepath)
        save_file = open(filepath, "ab")
        
        def update_data(begin, data):
            save_file.write(data)
            data_len = len(data)
            self.update_info["downloaded_size"] += data_len
            self.update_info["remain_size"] = self.file_size - self.update_info["downloaded_size"]
            
            current_time = time.time()
            self.update_info["average_speed"] = self.update_info["downloaded_size"] / (current_time - self.update_info["start_time"])
            self.update_info["update_time"] = current_time
            self.update_info["remain_time"] = (self.file_size - self.update_info["downloaded_size"]) / self.update_info["average_speed"]            
            self.update_info["realtime_size"] += data_len
            
            if self.update_info["remain_size"] == 0 or current_time - greenlet.info["realtime_time"] >= REALTIME_DELAY:
                self.update_info["realtime_speed"] = self.update_info["realtime_size"] / (current_time - greenlet.info["realtime_time"])
                self.update_info["realtime_time"] = current_time
                self.update_info["realtime_size"] = 0
            
                self.signal.emit("update", self.update_info)
            
            self.update_greenlet(begin, data)
            
        self.fetch.download_piece(
            self.buffer_size, 
            begin,
            end,
            update_data)    
        
        save_file.close()
        
        return begin

class FetchFiles(object):
    '''
    class docs
    '''
	
    def __init__(self,
                 file_urls,
                 file_hash_infos=None,
                 file_save_dir=None,
                 concurrent_num=5,
                 ):
        '''
        init docs
        '''
        self.file_urls = file_urls
        self.file_hash_infos = file_hash_infos
        self.file_save_dir = file_save_dir
        self.concurrent_num = concurrent_num
        
        self.greenlet_dict = {}
        self.fetch_file_dict = {}
        self.total_size = 0
        
        self.fetch_size_greenlet_dict = {}
        self.fetch_size_dict = {}
        
        self.signal = EventRegister()
        
        self.downloaded_size = 0
        self.update_time = -1
        
    def start(self):
        self.signal.emit("start")
        
        # Fetch file size.
        self.fetch_size_pool = Pool(self.concurrent_num)
        [self.start_fetch_size_greenlet(file_url) for file_url in self.file_urls]
        self.fetch_size_pool.join()
        
        # Fetch file.
        self.pool = Pool(self.concurrent_num)
        if self.file_hash_infos == None:
            file_infos = map(lambda file_url: (file_url, None), self.file_urls)
        else:
            file_infos = zip(self.file_urls, self.file_hash_infos)
        [self.start_greenlet(file_info) for file_info in file_infos]
        self.pool.join()
        
        self.signal.emit("finish")
        
    def stop(self, pause_flag=False):
        for greenlet in self.fetch_size_greenlet_dict.values():
            greenlet.kill()
            
        self.fetch_size_pool.kill()    
        
        for fetch_file in self.fetch_file_dict.values():
            fetch_file.stop(pause_flag)
        
        for greenlet in self.greenlet_dict.values():
            greenlet.kill()
            
        self.pool.kill()    
        
        if pause_flag:
            self.signal.emit("pause")
        else:
            self.signal.emit("stop")
        
    def pause(self):
        self.stop(True)
        
    def update(self, update_info):
        current_time = time.time()
        
        if current_time - self.update_time > 1:
            downloaded_size = 0
            for fetch_file in self.fetch_file_dict.values():
                if hasattr(fetch_file, "update_info"):
                    downloaded_size += fetch_file.update_info["downloaded_size"]
                    
            if self.update_time == -1:
                speed = 0
            else:
                speed = float(downloaded_size - self.downloaded_size) / (current_time - self.update_time)
                
            self.update_time = current_time
            self.downloaded_size = downloaded_size
                    
            self.signal.emit("update", 
                             (float(self.downloaded_size) / self.total_size) * 100, 
                             int(speed))
        
    def start_greenlet(self, (file_url, file_hash_info)):
        fetch_file = FetchFile(
            file_url=file_url,
            file_hash_info=file_hash_info,
            file_save_dir=self.file_save_dir,
            file_size=self.fetch_size_dict[file_url].file_size,
            )
        fetch_file.signal.register_event("update", self.update)
        
        greenlet = Greenlet(lambda f: f.start(), fetch_file)
        
        self.fetch_file_dict[file_url] = fetch_file
        self.greenlet_dict[file_url] = greenlet
        self.pool.start(greenlet)
        
    def fetch_file_size(self, fetch_file):
        fetch_file.init_file_size()
        
        self.total_size += fetch_file.file_size
        
    def start_fetch_size_greenlet(self, file_url):
        fetch_file = FetchFile(file_url=file_url)
        
        greenlet = Greenlet(self.fetch_file_size, fetch_file)
        self.fetch_size_dict[file_url] = fetch_file        
        self.fetch_size_greenlet_dict[file_url] = greenlet
        self.fetch_size_pool.start(greenlet)
        
class FetchService(object):
    '''
    class docs
    '''
	
    def __init__(self, concurrent_num):
        '''
        init docs
        '''
        self.concurrent_num = concurrent_num
        self.signal = Queue()
        self.pool = Pool(self.concurrent_num)
        self.fetch_dict = {}
        
    def add_fetch(self, fetch_files):
        self.signal.put(("add", fetch_files))
    
    def stop_fetch(self, fetch_files):
        self.signal.put(("stop", fetch_files))

    def pause_fetch(self, fetch_files):
        self.signal.put(("pause", fetch_files))
        
    def exit(self):
        self.signal.put("exit")
    
    def run(self):
        signal = self.signal.get()
        
        if signal == "exit":
            return 
        else:
            (action, fetch_files) = signal
            if action == "add":
                self.fetch_dict[fetch_files] = Greenlet(lambda : fetch_files.start())
                self.pool.start(self.fetch_dict[fetch_files])
            elif action == "stop":
                if self.fetch_dict.has_key(fetch_files):
                    fetch_files.stop()
                    self.fetch_dict.pop(fetch_files)
            elif action == "pause":
                if self.fetch_dict.has_key(fetch_files):
                    fetch_files.pause()
                    self.fetch_dict.pop(fetch_files)
            
            self.run()
        
class FetchServiceThread(td.Thread):
    '''
    class docs
    '''
	
    def __init__(self, concurrent_num):
        '''
        init docs
        '''
        td.Thread.__init__(self)
        self.setDaemon(True)    # make thread exit when main program exit
        self.fetch_service = FetchService(concurrent_num)
        
    def run(self):
        self.fetch_service.run()
        
def join_glib_loop():
    import gtk
    import gobject
    import gevent
    import sys
    
    def idle():
        try:
            gevent.sleep(0.01)
        except:
            gtk.main_quit()
            gevent.hub.MAIN.throw(*sys.exc_info())
        return True
    
    gobject.idle_add(idle)
        
if __name__ == "__main__":
    import gtk
    # import gobject
    
    gtk.gdk.threads_init()
    
    thread = FetchServiceThread(5)
    thread.start()
    
    join_glib_loop()
    
    fetch_files_1 = FetchFiles([
            "ftp://ftp.sjtu.edu.cn/ubuntu-cd/quantal/wubi.exe",
            # "ftp://ftp.sjtu.edu.cn/ubuntu-cd/12.04/ubuntu-12.04.1-alternate-amd64.iso",
            # "http://test.packages.linuxdeepin.com/deepin/pool/main/d/deepin-media-player/deepin-media-player_1+git201209111105_all.deb",
            ])
    
    fetch_files_2 = FetchFiles([
            "http://test.packages.linuxdeepin.com/ubuntu/pool/main/v/vim/vim_7.3.429-2ubuntu2.1_amd64.deb",
            ])
    
    thread.fetch_service.add_fetch(fetch_files_1)
    # gobject.timeout_add(2000, lambda : thread.fetch_service.add_fetch(fetch_files_1))
    # gobject.timeout_add(3000, lambda : thread.fetch_service.add_fetch(fetch_files_2))
    # gobject.timeout_add(4000, lambda : thread.fetch_service.stop_fetch(fetch_files_1))
    # gobject.timeout_add(8000, lambda : thread.fetch_service.add_fetch(fetch_files_1))
    # gobject.timeout_add(9000, lambda : thread.fetch_service.pause_fetch(fetch_files_1))
    
    gtk.main()

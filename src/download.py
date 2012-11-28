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
import gevent
from gevent import monkey, Greenlet
from gevent.pool import Pool
monkey.patch_all()

from events import EventRegister
import urlparse
import sys
import gobject
import time
from http import FetchHttp
from ftp import FetchFtp
import os

STATUS_WAITING = 0
STATUS_DOWNLOADING = 1
STATUS_FINISH = 2

class FetchFile(object):
    '''
    class docs
    '''
	
    def __init__(self,
                 file_url,
                 file_save_path,
                 file_hash_info=None,
                 concurrent_num=10,
                 buffer_size=8192, # in byte
                 min_split_size=20480, # in byte
                 ):
        '''
        init docs
        '''
        self.file_url = file_url
        self.file_save_path = file_save_path
        (self.file_save_dir, self.file_name) = os.path.split(file_save_path)
        self.concurrent_num = concurrent_num
        self.file_hash_info = file_hash_info
        self.buffer_size = buffer_size
        self.min_split_size = min_split_size
        self.fetch = self.get_fetch()
        
        self.update_greenlet_callbacks = []
        
        self.signal = EventRegister()
        
    def get_fetch(self):
        url = urlparse.urlparse(self.file_url)
        if url[0] == "http":
            return FetchHttp(self.file_url)
        elif url[0] == "ftp":
            return FetchFtp(self.file_url)
        
    def get_piece_ranges(self):    
        if self.file_size < self.min_split_size:
            return [(0, self.file_size - 1)]
        else:
            if self.file_size < self.min_split_size * self.concurrent_num:
                split_size = self.min_split_size
            else:
                split_size = self.file_size / self.concurrent_num
                
            ranges = []
            for index in xrange(self.concurrent_num - 1):
                ranges.append(((index * split_size), (index + 1) * split_size - 1))
                
            ranges.append(((self.concurrent_num - 1) * split_size, self.file_size - 1))
            
            return ranges
        
    def start(self):
        self.file_size = self.fetch.get_file_size()
        
        if self.file_size > 0:
            current_time = time.time()
            self.update_info = {
                "file_size" : self.file_size,
                "downloaded_size" : 0,
                "start_time" : current_time,
                "update_time" : current_time,
                "remain_time" : -1,
                "average_speed" : -1,
                "realtime_speed" : -1
                }
            
            piece_ranges = self.get_piece_ranges()
            
            self.greenlet_dict = {}
            for (begin, end) in piece_ranges:
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
                    "realtime_speed" : -1,       # realtime speed
                    "remain_time" : -1           # remain time
                    }
                self.greenlet_dict[begin] = greenlet
            
            self.pool = Pool(self.concurrent_num)
            # self.pool = Pool(3)
            [self.pool.start(greenlet) for greenlet in self.greenlet_dict.values()]
            self.pool.join()
            
            print "Finish download."
        else:
            print "File size of %s is 0" % (self.file_url)
            
    def finish(self, greenlet):
        print "Finish: %s" % greenlet.info["id"]
        print self.pool.wait_available()
        
    def update_greenlet(self, begin, data):
        data_len = len(data)
        greenlet = self.greenlet_dict[begin]
        current_time = time.time()
        remain_size = greenlet.info["remain_size"] - data_len
        realtime_speed = data_len / (current_time - greenlet.info["update_time"])
        average_speed = (greenlet.info["range_size"] - remain_size) / (current_time - greenlet.info["start_time"])
        
        greenlet.info["remain_size"] = remain_size
        greenlet.info["update_time"] = current_time
        greenlet.info["average_speed"] = average_speed
        greenlet.info["realtime_speed"] = realtime_speed
        greenlet.info["remain_time"] = remain_size / average_speed
        
        self.signal.emit("update_greenlet", greenlet.info)
        
    def update(self, (begin, end)):
        self.signal.emit("start_greenlet", begin)
        
        current_time = time.time()
        greenlet = self.greenlet_dict[begin]
        greenlet.info["status"] = STATUS_DOWNLOADING
        greenlet.info["range_size"] = end - begin
        greenlet.info["remain_size"] = end - begin
        greenlet.info["start_time"] = current_time
        greenlet.info["update_time"] = current_time
        
        filepath = "%s_%s" % (self.file_save_path, begin)
        
        from dtk.ui.utils import remove_file
        remove_file(filepath)
        save_file = open(filepath, "ab")
        
        def update_data(begin, data):
            save_file.write(data)
            data_len = len(data)
            self.update_info["downloaded_size"] += data_len
            
            current_time = time.time()
            self.update_info["average_speed"] = self.update_info["downloaded_size"] / (current_time - self.update_info["start_time"])
            self.update_info["realtime_speed"] = data_len / (current_time - self.update_info["update_time"])
            self.update_info["update_time"] = current_time
            self.update_info["remain_time"] = (self.file_size - self.update_info["downloaded_size"]) / self.update_info["average_speed"]            
            
            self.signal.emit("update", self.update_info)
            
            self.update_greenlet(begin, data)
            
        self.fetch.download_piece(
            self.buffer_size, 
            begin,
            end,
            update_data)    
        
        save_file.close()
        
        return begin
    
def unzip(unzip_list):
    '''
    Unzip [(1, 'a'), (2, 'b'), (3, 'c')] to ([1, 2, 3], ['a', 'b', 'c']).
    
    @param unzip_list: List to unzip.
    @return: Return new unzip list.
    '''
    return tuple(map(list, zip(*unzip_list))) 

from threads import post_gui

@post_gui
def update_greenlet_plot(plot, value):
    plot.update(value["id"], value["update_time"], value["average_speed"])
    
@post_gui
def update_plot(plot, value):
    # print divmod(int(value["remain_time"]), 60)
    plot.update("total", value["update_time"], value["average_speed"])
    
import threading as td

class TestThread(td.Thread):
    '''
    class docs
    '''
	
    def __init__(self, plot):
        '''
        init docs
        '''
        td.Thread.__init__(self)
        self.setDaemon(True)    # make thread exit when main program exit
        
        self.plot = plot

    def run(self):
        fetch_file = FetchFile(
            # "ftp://ftp.sjtu.edu.cn/ubuntu-cd/quantal/wubi.exe",
            # "http://test.packages.linuxdeepin.com/ubuntu/pool/main/v/vim/vim_7.3.429-2ubuntu2.1_amd64.deb",
            # "http://test.packages.linuxdeepin.com/deepin/pool/main/d/deepin-media-player/deepin-media-player_1+git201209111105_all.deb",
            "http://cdimage.linuxdeepin.com/daily-live/desktop/20121124/deepin-desktop-amd64.iso",
            # "http://test.packages.linuxdeepin.com/deepin/pool/main/d/deepin-emacs/deepin-emacs_1.1-1_all.deb",
            # "ftp://ftp.sjtu.edu.cn/ubuntu-cd/12.04/ubuntu-12.04.1-alternate-amd64.iso",
            "/tmp/deepin-desktop-adm64.iso",
            )
        self.plot.add_axes("total")
        fetch_file.signal.register_event("start_greenlet", lambda greenlet_id: self.plot.add_axes(greenlet_id))
        fetch_file.signal.register_event("update_greenlet", lambda v: update_greenlet_plot(self.plot, v))
        fetch_file.signal.register_event("update", lambda v: update_plot(self.plot, v))
        fetch_file.start()
    
if __name__ == "__main__":
    # FetchFile(
    #     "http://cdimage.linuxdeepin.com/daily-live/desktop/20121124/deepin-desktop-amd64.iso",
    #     "./deepin-desktop-amd64.iso").start()
    
    import gtk
    gtk.gdk.threads_init()
    
    from plot import Plot
    plot = Plot()
    
    TestThread(plot).start()
    
    def idle():
        try:
            gevent.sleep(0.01)
        except:
            gtk.main_quit()
            gevent.hub.MAIN.throw(*sys.exc_info())
        return True
    
    gobject.idle_add(idle)
    
    plot.run()

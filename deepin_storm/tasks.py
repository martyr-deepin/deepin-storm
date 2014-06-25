#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 ~ 2012 Deepin, Inc.
#               2011 ~ 2012 Hou Shaohui
# 
# Author:     Hou Shaohui <houshao55@gmail.com>
# Maintainer: Hou Shaohui <houshao55@gmail.com>
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

import os
import time
import threading
import sys
import traceback

from .report import ProgressBar, parse_bytes
from .state import ConnectionState
from .fetch import provider_manager
from .events import EventManager

from . import common

class StopExcetion(Exception):
    pass

class PauseException(Exception):
    pass

class ResumeException(Exception):
    pass

class TaskObject(EventManager):
    
    def __init__(self, url, output_file=None, num_connections=4, max_speed=None,
            verbose=False, output_temp=False, update_interval=1, task_name=None):
        EventManager.__init__(self)

        self.url = url
        self.output_file = self.get_output_file(output_file)
        self.num_connections = num_connections
        self.task_name = common.get_task_id(url) if not task_name else task_name

        self.max_speed = max_speed
        self.conn_state = None
        self.fetch_threads = []
        self.__stop = True
        self.__pause = False
        self.__finish = False
        self.verbose = verbose
        self.output_temp = output_temp
        self.update_interval = update_interval
        self.update_object = common.Storage()
        self.task_thread = None
        
        self.RemoteFetch = None
        fetchs = provider_manager.get("fetch")
        
        for fetch in fetchs:        
            if fetch.is_match(url):
                self.RemoteFetch = fetch
                break

    def fetch_thread_error_update(self, thread, error_info):
        if thread in self.fetch_threads:
            self.fetch_threads.remove(thread)

        if len(self.fetch_threads) == 0:
            self.emit("error", "%s task occur error with %s" % (self.task_name, error_info), self)

    def get_task_id(self):
        pass
        
    def get_output_file(self, output_file):    
        if output_file is not None:
            return output_file
        
        return self.url.rsplit("/", 1)[1]
    
    def emit_update(self):
        dl_len = 0
        for rec in self.conn_state.progress:
            dl_len += rec
            
        try:    
            avg_speed = dl_len / self.conn_state.elapsed_time
        except:    
            avg_speed = 0
            
        self.update_object.speed = avg_speed    
        self.update_object.progress = dl_len * 100 / self.conn_state.filesize
        self.update_object.remaining = (self.conn_state.filesize - dl_len) / avg_speed if avg_speed > 0 else 0
        self.update_object.filesize = self.conn_state.filesize
        self.update_object.downloaded = dl_len
        
        self.emit("update", self.update_object, self)
        
    def is_actived(self):    
        for task in self.fetch_threads:
            if task.isAlive():
                return True
        return False    
    
    def stop_all_task(self):
        for task in self.fetch_threads:
            task.need_to_quit = True
            
    def stop(self):        
        self.__stop = True
        self.task_thread = None
        
    def pause(self):    
        self.__pause = True
        
    def resume(self):
        if self.task_thread is None:
            self.emit("resume", obj=self)
            self.start()
        
    def isfinish(self):    
        return self.__finish
    
    def start(self):
        self.task_thread = threading.Thread(target=self.run)
        self.task_thread.setDaemon(True)
        self.task_thread.start()
            
    def run(self):    
        try:
            if self.RemoteFetch is None:
                error_info = "Don't support the protocol"
                self.logerror(error_info)
                self.emit("error", error_info, self)
                return 
            
            if not self.output_file:
                error_info = "Invalid URL"
                self.logerror(error_info)
                self.emit("error", error_info, self)
                return

            
            self.__stop = False
            self.__pause = False
            
            file_size = self.RemoteFetch.get_file_size(self.url)
            if file_size == 0:
                error_info = "Failed to get file information"
                self.logerror("UEL: %s, %s", self.url, error_info)
                self.emit("error", error_info, self)
                return

            if os.path.exists(self.output_file):
                self.update_object.speed = -1
                self.update_object.progress = 100
                self.update_object.remaining = 0
                self.update_object.filesize = file_size
                self.update_object.downloaded = file_size
                self.emit("update", self.update_object, self)
                self.emit("finish", obj=self)
                return

            if self.output_temp:
                part_output_file = common.get_temp_file(self.url)
            else:
                part_output_file = "%s.part" % self.output_file
            
            self.emit("start", obj=self)
            
            # load ProgressBar.
            # if file_size < BLOCK_SIZE:
            #     num_connections = 1
            # else:    
            num_connections = self.num_connections
             
            # Checking if we have a partial download available and resume
            self.conn_state = ConnectionState(num_connections, file_size)    
            state_file = common.get_state_file(self.url)
            self.conn_state.resume_state(state_file, part_output_file)
            
            
            self.report_bar = ProgressBar(num_connections, self.conn_state)
            
            self.logdebug("File: %s, need to fetch %s", self.output_file, 
                         parse_bytes(self.conn_state.filesize - sum(self.conn_state.progress)))
            
            #create output file with a .part extension to indicate partial download

            part_output_file_fp = os.open(part_output_file, os.O_CREAT | os.O_WRONLY)
            os.close(part_output_file_fp)
            
            start_offset = 0
            start_time = time.time()

            for i in range(num_connections):
                current_thread = self.RemoteFetch(i, self.url, part_output_file, state_file, 
                                           start_offset + self.conn_state.progress[i],
                                           self.conn_state, self)
                self.fetch_threads.append(current_thread)
                current_thread.start()
                start_offset += self.conn_state.chunks[i]

            while self.is_actived():
                if self.__stop:
                    raise StopExcetion

                if self.__pause:
                    raise PauseException

                end_time = time.time()
                self.conn_state.update_time_taken(end_time-start_time)
                start_time = end_time

                download_sofar = self.conn_state.download_sofar()

                if self.max_speed != None and \
                        (download_sofar / self.conn_state.elapsed_time) > (self.max_speed * 1204):
                    for task in self.fetch_threads:
                        task.need_to_sleep = True
                        task.sleep_timer = download_sofar / (self.max_speed * 1024 - self.conn_state.elapsed_time)

                # update progress
                if self.verbose:
                    self.report_bar.display_progress()
                self.emit_update()
                time.sleep(self.update_interval)

            if len(self.fetch_threads) == 0:
                raise StopExcetion

            if self.verbose:
                self.report_bar.display_progress()

            try:
                os.remove(state_file)
                os.unlink(self.output_file)
            except:
                pass

            os.rename(part_output_file, self.output_file)
            self.__finish = True
            self.emit_update()
            self.emit("finish", obj=self)
            if self.verbose:
                self.report_bar.display_progress()

        except StopExcetion:
            self.stop_all_task()

            try:
                os.unlink(part_output_file)
            except: pass

            try:
                os.unlink(state_file)
            except: pass
            
            self.emit("stop", obj=self)
            
        except PauseException:    
            self.stop_all_task()
            self.emit("pause", obj=self)
            
        except KeyboardInterrupt, e:    
            self.emit("stop", obj=self)
            self.stop_all_task()
            
        except Exception, e:
            self.emit("error", "Unknown error", self)
            self.emit("stop", obj=self)
            traceback.print_exc(file=sys.stdout)
            self.logdebug("File: %s at dowloading error %s", self.output_file, e)
            self.stop_all_task()

class MultiTaskObject(EventManager):
    """
        make multi task like one task
    """
    def __init__(self, urls, output_dir=None, num_connections=2, 
            update_interval=1, task_name=None):
        EventManager.__init__(self)

        self.urls = urls
        self.output_dir = output_dir
        self.num_connections = num_connections
        self.update_interval = update_interval
        self.task_name = common.get_task_id(urls) if not task_name else task_name

        self.__stop = True
        self.__pause = False
        self.__finish = False
        self.task_thread = None
        self.start_time = None

        self.update_object = common.Storage()
        self.__downloaded_size = 0
        self.__last_downloaded = 0

        self.total_size = 0
        self.active_task_list = []
        self.wait_task_list = []
        self.all_task_list = []
        self.task_finish_list = []
        self.init_tasks()

    def init_tasks(self):
        for url in self.urls:
            task = TaskObject(url, update_interval=0.2)
            task.connect("update", self.update_tasks)
            task.connect("pause", self.pause_tasks)
            task.connect("stop", self.stop_tasks)
            task.connect("finish", self.finish_tasks)
            task.connect("resume", self.resume_tasks)
            task.connect("error", self.emit_error)
            self.all_task_list.append(task)

    def stop(self):
        self.__stop = True
        self.task_thread = None
        self.stop_all_task()

    def stop_all_task(self):
        for task in self.all_task_list:
            task.stop()

    def is_actived(self):
        return len(self.task_finish_list) != len(self.urls)

    def update_tasks(self, task, data):
        pass

    def pause_tasks(self, task, data):
        pass

    def stop_tasks(self, task, data):
        pass

    def finish_tasks(self, task, data):
        if task in self.active_task_list:
            task.disconnect("update", self.update_tasks)
            task.disconnect("pause", self.pause_tasks)
            task.disconnect("stop", self.stop_tasks)
            task.disconnect("finish", self.finish_tasks)
            task.disconnect("resume", self.resume_tasks)
            task.disconnect("error", self.emit_error)
            self.active_task_list.remove(task)
            if task not in self.task_finish_list:
                self.task_finish_list.append(task)
        self.wake_up_wait_tasks()

    def wake_up_wait_tasks(self):
        for task in self.wait_task_list:
            # Just break loop when active task is bigger than max value.
            if len(self.active_task_list) >= self.num_connections:
                break
            # Otherwise add task from wait list.
            else:
                # Remove from wait list.
                if task in self.wait_task_list:
                    self.wait_task_list.remove(task)
                    if task not in self.active_task_list:
                        self.active_task_list.append(task)
                        task.start()

    def resume_tasks(self, task, data):
        pass

    def emit_error(self, task, error_info):
        self.logerror(error_info)
        self.emit("error", error_info, self)
        self.__stop = True
        self.task_thread = None

    def emit_update(self):
        dl_len = 0
        valid_len = 0
        for task in self.all_task_list:
            if task.update_object:
                dl_len += task.update_object.downloaded
                if task.update_object.speed != -1:
                    valid_len += task.update_object.downloaded

        if self.__last_downloaded == 0:
            self.__last_downloaded = valid_len
        self.__downloaded_size += valid_len - self.__last_downloaded
        self.__last_downloaded = valid_len
        now = time.time()
        elapsed_time = now - self.start_time

        try:
            avg_speed = self.__downloaded_size / elapsed_time
        except:
            avg_speed = 0

        # TODO: speed
        self.update_object.speed = avg_speed
        self.update_object.progress = dl_len * 100 / self.total_size
        self.update_object.remaining = (self.total_size - dl_len) / avg_speed if avg_speed > 0 else 0
        self.update_object.filesize = self.total_size
        self.update_object.downloaded = dl_len

        self.emit("update", self.update_object, self)

    def start(self):
        self.task_thread = threading.Thread(target=self.run)
        self.task_thread.setDaemon(True)
        self.task_thread.start()

    def run(self):
        try:
            self.emit("start", obj=self)
            self.start_time = time.time()

            for (index, task) in enumerate(self.all_task_list):
                if task.RemoteFetch is None:
                    error_info = "Don't support the protocol"
                    self.logerror(error_info)
                    error_list = [error_info, task]
                    self.emit("error", error_list, self)
                    return

                if not task.output_file:
                    error_info = "Invalid URL"
                    self.logerror(error_info)
                    error_list = [error_info, task]
                    self.emit("error", error_list, self)
                    return

                file_size = task.RemoteFetch.get_file_size(task.url)
                if file_size == 0:
                    error_info = "Failed to get file information"
                    self.logerror("UEL: %s, %s", task.url, error_info)
                    error_list = [error_info, task]
                    self.emit("error", error_list, self)
                    return
                else:
                    self.total_size += file_size

                if self.output_dir:
                    task.output_file = os.path.join(self.output_dir, task.output_file)

                if len(self.active_task_list) >= self.num_connections:
                    self.wait_task_list += self.all_task_list[index:]
                else:
                    self.active_task_list.append(task)
                    task.start()

            self.__stop = False
            self.__pause = False

            while self.is_actived():
                if self.__stop:
                    raise StopExcetion

                if self.__pause:
                    raise PauseException

                if len(self.active_task_list) >= self.num_connections:
                    pass

                self.emit_update()
                time.sleep(self.update_interval)

            self.emit_update()
            self.emit("finish", obj=self)
            self.logdebug("%s task finished" % self.task_name)

        except StopExcetion:
            self.stop_all_task()
            self.emit("stop", obj=self)
            self.logdebug("%s task stopped" % self.task_name)

        except PauseException:
            self.stop_all_task()
            self.emit("pause", obj=self)
            self.logdebug("%s task paused" % self.task_name)

        except KeyboardInterrupt, e:
            self.emit("stop", obj=self)
            self.stop_all_task()
            self.logdebug("%s task stopped" % self.task_name)

        except Exception, e:
            self.stop_all_task()
            self.emit("error", "Unknown error", self)
            self.emit("stop", obj=self)
            self.logerror("MultiTask: %s at dowloading error %s", self.urls, e)
            traceback.print_exc(file=sys.stdout)

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

import gevent
from gevent import monkey
monkey.patch_all()

import threading as td
from download import FetchService, FetchFiles
import gtk
import gobject
import sys

def idle():
    try:
        gevent.sleep(0.01)
    except:
        gtk.main_quit()
        gevent.hub.MAIN.throw(*sys.exc_info())
    return True

class TestThread(td.Thread):
    '''
    class docs
    '''
	
    def __init__(self):
        '''
        init docs
        '''
        td.Thread.__init__(self)
        self.setDaemon(True)    # make thread exit when main program exit
        
        self.fetch_service = FetchService(5)
        
    def add_fetch(self, fetch_files):
        self.fetch_service.add_fetch(fetch_files)
        
    def stop_fetch(self, fetch_files):
        self.fetch_service.stop_fetch(fetch_files)
        
    def pause_fetch(self, fetch_files):
        self.fetch_service.pause_fetch(fetch_files)
        
    def run(self):
        self.fetch_service.run()
        
        print "*****"

gtk.gdk.threads_init()

thread = TestThread()
thread.start()

gobject.idle_add(idle)

fetch_files_1 = FetchFiles([
        "http://test.packages.linuxdeepin.com/deepin/pool/main/d/deepin-media-player/deepin-media-player_1+git201209111105_all.deb",
        ])

fetch_files_2 = FetchFiles([
        "http://test.packages.linuxdeepin.com/ubuntu/pool/main/v/vim/vim_7.3.429-2ubuntu2.1_amd64.deb",
        ])

gobject.timeout_add(2000, lambda : thread.add_fetch(fetch_files_1))
gobject.timeout_add(3000, lambda : thread.add_fetch(fetch_files_2))
gobject.timeout_add(4000, lambda : thread.stop_fetch(fetch_files_1))
gobject.timeout_add(8000, lambda : thread.add_fetch(fetch_files_1))
gobject.timeout_add(9000, lambda : thread.pause_fetch(fetch_files_1))

gtk.main()

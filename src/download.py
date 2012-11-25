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
from gevent import monkey
monkey.patch_all()

import urlparse
from http import FetchHttp
from ftp import FetchFtp
import os

class FetchFile(object):
    '''
    class docs
    '''
	
    def __init__(self,
                 file_url,
                 file_save_path,
                 file_hash_info=None,
                 concurrent_threads=5,
                 buffer_size=8192, # in byte
                 min_split_size=20480, # in byte
                 ):
        '''
        init docs
        '''
        self.file_url = file_url
        self.file_save_path = file_save_path
        (self.file_save_dir, self.file_name) = os.path.split(file_save_path)
        self.concurrent_threads = concurrent_threads
        self.file_hash_info = file_hash_info
        self.buffer_size = buffer_size
        self.min_split_size = min_split_size
        self.fetch = self.get_fetch()
        
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
            if self.file_size < self.min_split_size * self.concurrent_threads:
                split_size = self.min_split_size
            else:
                split_size = self.file_size / self.concurrent_threads
                
            ranges = []
            for index in xrange(self.concurrent_threads - 1):
                ranges.append(((index * split_size), (index + 1) * split_size - 1))
                
            ranges.append(((self.concurrent_threads - 1) * split_size, self.file_size - 1))
            
            return ranges
        
    def start(self):
        self.file_size = self.fetch.get_file_size()
        
        if self.file_size > 0:
            self.downloaded_size = 0
            download_piece_jobs = [gevent.spawn(self.fetch.download_piece, 
                                                self.buffer_size, 
                                                download_range,
                                                self.file_save_path,
                                                self.update,
                                                ) 
                                   for download_range in self.get_piece_ranges()]
            
            gevent.joinall(download_piece_jobs)
            
            print "Finish download."
        else:
            print "File size of %s is 0" % (self.file_url)
            
    def update(self, data_len):        
        self.downloaded_size += data_len
        print self.downloaded_size / float(self.file_size) * 100

if __name__ == "__main__":
    FetchFile(
        # "ftp://ftp.sjtu.edu.cn/ubuntu-cd/quantal/ubuntu-12.10-wubi-i386.tar.xz",
        "http://test.packages.linuxdeepin.com/ubuntu/pool/main/v/vim/vim_7.3.429-2ubuntu2.1_amd64.deb",
        # "http://cdimage.linuxdeepin.com/daily-live/desktop/20121124/deepin-desktop-amd64.iso",
        # "ftp://ftp.sjtu.edu.cn/ubuntu-cd/12.04/ubuntu-12.04.1-alternate-amd64.iso",
        "./deepin-desktop-adm64.iso",
        ).start()

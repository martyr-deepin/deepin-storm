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

import urllib2
import traceback
import sys

class FetchHttp(object):
    '''
    class docs
    '''
	
    def __init__(self, file_url):
        '''
        init docs
        '''
        self.file_url = file_url
        
    def get_file_size(self):
        try:
            conn = urllib2.urlopen(self.file_url)
            return int(conn.info().getheaders("Content-Length")[0])
        except Exception, e:
            print "get_file_size got error: %s" % e
            traceback.print_exc(file=sys.stdout)
            
            return 0
        
    def download_piece(self, buffer_size, (start, end), file_save_path, update_callback):
        download_finish = False
        retries = 1
        current_pos = start
        while not download_finish:
            if retries > 10:
                break
            
            try:
                request = urllib2.Request(self.file_url)
                request.add_header("Range", "bytes=%d-%d" % (start, end))
                conn = urllib2.urlopen(request)
                data = conn.read(buffer_size)
                save_file = open("%s_%s" % (file_save_path, start), "ab")
                while data:
                    save_file.write(data)
                    
                    data_len = len(data)
                    current_pos += data_len
                    update_callback(data_len)
                    
                    data = conn.read(buffer_size)
                    
                if save_file and not save_file.closed:
                    save_file.close()
                    
                download_finish = True    
            except Exception, e:
                print "Retries: %s: %s (%s)" % (start, retries, e)
                traceback.print_exc(file=sys.stdout)
                
                retries += 1
                gevent.sleep(1)
                continue
            
            


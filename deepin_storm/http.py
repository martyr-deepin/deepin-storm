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
from patch import gevent_patch
gevent_patch()

import gevent
from gevent import GreenletExit

import urllib2
import traceback
import sys

class FetchHttp(object):
    '''
    class docs
    '''
	
    def __init__(self, 
                 file_url, 
                 timeout=60):
        '''
        init docs
        '''
        self.file_url = file_url
        self.timeout = timeout
        
    def get_file_size(self):
        try:
            conn = urllib2.urlopen(self.file_url, timeout=self.timeout)
            size = int(conn.info().getheaders("Content-Length")[0])
            conn.close()
            return size
        except Exception, e:
            print "get_file_size got error: %s" % e
            traceback.print_exc(file=sys.stdout)
            
            raise e
            
            return 0
        
    def download_piece(self, buffer_size, begin, end, update_callback):
        # Init.
        retries = 1
        remaining = end - begin + 1
        
        # Connection.
        request = urllib2.Request(self.file_url)
        request.add_header("Range", "bytes=%d-%d" % (begin, end))
        conn = urllib2.urlopen(request, timeout=self.timeout)
            
        # Start download.
        while True:
            if retries > 10:
                break
            
            try:
                read_size = min(buffer_size, remaining)
                if read_size <= 0:
                    break
                
                data = conn.read(read_size)
                
                if not data:
                    break
                
                remaining -= len(data)
                update_callback(begin, data)
                retries = 1
            except GreenletExit:
                # Drop received data when greenlet killed.
                break
            except Exception, e:
                print "Retries: %s(%s): %s (%s)" % (self.file_url, begin, retries, e)
                traceback.print_exc(file=sys.stdout)
                
                retries += 1
                gevent.sleep(1)
                continue
            
        # Clean work.
        conn.close()    

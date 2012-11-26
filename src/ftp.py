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
from gevent import monkey
monkey.patch_all()

from ftplib import FTP
import traceback
import sys
import urlparse

class FetchFtp(object):
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
            url = urlparse.urlparse(self.file_url)
            ftp = FTP(url[1])
            ftp.login()
            size = int(ftp.size(url[2]))
            ftp.quit()
            
            return size
        except Exception, e:
            print "get_file_size got error: %s" % e
            traceback.print_exc(file=sys.stdout)
            
            return 0

    def download_piece(self, buffer_size, (begin, end), file_save_path, update_callback):
        download_finish = False
        remaining = end - begin + 1
        while not download_finish:
            try:
                # Login.
                url = urlparse.urlparse(self.file_url)
                ftp = FTP(url[1])
                ftp.login()
                
                # Transfer data in binary mode.
                ftp.voidcmd("TYPE I")
                
                # Set offset.
                ftp.sendcmd("REST %s" % begin)
                
                # Start download.
                conn = ftp.transfercmd("RETR %s" % url[2])
                save_file = open("%s_%s" % (file_save_path, begin), "ab")

                while True:
                    read_size = min(buffer_size, remaining)
                    if read_size <= 0:
                        break
                    
                    data = conn.recv(read_size)
                    if not data:
                        break

                    
                    save_file.write(data)
                    data_len = len(data)
                    remaining -= data_len                    
                    update_callback(data_len)
                    
                save_file.close()
                conn.close()    
                download_finish = True
            except Exception, e:
                print "download_piece got error: %s" % e
                traceback.print_exc(file=sys.stdout)
                
                break

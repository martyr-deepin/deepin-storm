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
            return int(ftp.size(url[2]))
        except Exception, e:
            print "get_file_size got error: %s" % e
            traceback.print_exc(file=sys.stdout)
            
            return 0

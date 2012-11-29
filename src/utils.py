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

import os

def remove_file(path):
    '''
    Remove file if file exist.
    
    @param path: Target path to remove.
    '''
    if os.path.exists(path):
        os.remove(path)
        
def create_directory(directory, remove_first=False):
    '''
    Create directory.
    
    @param directory: Target directory to create.
    @param remove_first: If you want remove directory when directory has exist, set it as True.
    '''
    if remove_first and os.path.exists(directory):
        remove_directory(directory)
    
    if not os.path.exists(directory):
        os.makedirs(directory)
        
def remove_directory(path):
    """
    Remove directory recursively, equivalent to command `rm -rf path`.

    @param path: Target directory to remove.
    """
    if os.path.exists(path):
        for i in os.listdir(path):
            full_path = os.path.join(path, i)
            if os.path.isdir(full_path):
                remove_directory(full_path)
            else:
                os.remove(full_path)
        os.rmdir(path)        

def unzip(unzip_list):
    '''
    Unzip [(1, 'a'), (2, 'b'), (3, 'c')] to ([1, 2, 3], ['a', 'b', 'c']).
    
    @param unzip_list: List to unzip.
    @return: Return new unzip list.
    '''
    return tuple(map(list, zip(*unzip_list))) 


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

from distutils.core import setup

setup(
    name            = 'deepin-storm',
    version         = '0.3',
    description     = 'Python download library and Powerful download manager',
    long_description= 'Deepin Storm is download library and powerful download manager',
    author          = 'Alan Leaf',
    author_email    = 'alan.leaf916@gmail.com',
    url             = 'https://github.com/linuxdeepin/deepin-storm',
    license         = 'GPL-3',
    platforms       = ['all'],
    packages        = ['deepin_storm']
    )

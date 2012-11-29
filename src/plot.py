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

import gtk
import md5
import math
from matplotlib.backends.backend_gtk import FigureCanvasGTK as FigureCanvas
from matplotlib.figure import Figure

def hex_to_color(r, g, b):
    return math.floor(float(r * 0.2999 + g * 0.587 + b * 0.114) / 256)

def get_id_color(axes_id):
    color_hex_string = md5.new(str(axes_id)).hexdigest()[0:12]
    (r_str, g_str, b_str) = color_hex_string[0:4], color_hex_string[4:8], color_hex_string[8:12]
    r, g, b = int(r_str, 16) / 255, int(g_str, 16) / 255, int(b_str, 16) / 255
    
    return "#%02X%02X%02X" % (r, g, b)

class Plot(object):
    '''
    class docs
    '''
	
    def __init__(self):
        '''
        init docs
        '''
        self.window = gtk.Window()
        self.window.connect("destroy", lambda x: gtk.main_quit())
        self.window.set_default_size(800, 600)
        
        self.figure = Figure()
        self.axes_dict = {}
        
        self.canvas = FigureCanvas(self.figure)
        self.window.add(self.canvas)
        
        self.redraw = False
        
        gtk.timeout_add(200, self.expose)
        
    def add_axes(self, axes_id, greenlet_info):    
        ax = self.figure.add_subplot(111)
        ax.set_ylim([-1, 601])
        ax.grid(True)
        ax.set_yticks(range(0, 601, 50))
        
        self.axes_dict[axes_id] = {
            "axes" : ax,
            "axes_color" : get_id_color(axes_id),
            "x_values" : [greenlet_info["update_time"]],
            "y_values" : [0],
            }
        
    def update(self, axes_id, x, y):
        axes_info = self.axes_dict[axes_id]
        axes_info["x_values"].append(x)
        axes_info["y_values"].append(int(y / 1024))
        
        self.redraw = True
        
    def expose(self):
        if self.redraw:
            for (axes_id, axes_info) in self.axes_dict.items():
                ax = axes_info["axes"]
                ax.plot(
                    axes_info["x_values"],
                    axes_info["y_values"],
                    color=axes_info["axes_color"],
                    label=str(axes_id),
                    lw=2,
                    )
                
                try:
                    lim_length = 10
                    if len(axes_info["x_values"]) > 0:
                        current_time = int(axes_info["x_values"][-1])
                        xlim = [(max(0, current_time - lim_length), current_time + 1)]
                    else:
                        xlim = [(0, lim_length + 1)]
                    ax.set_xlim(xlim)
                    ax.set_xticks(range(xlim[0], xlim[1], 1))
                except:
                    pass
                
            self.figure.canvas.draw()
                
            self.redraw = False
            
        return True
    
    def run(self):
        self.window.show_all()
        gtk.main()

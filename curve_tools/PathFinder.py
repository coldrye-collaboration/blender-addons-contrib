# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and / or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    'name': 'PathFinder',
    'author': 'Spivak Vladimir (http://cwolf3d.korostyshev.net)',
    'version': (0, 5, 0),
    'blender': (2, 80, 0),
    'location': 'Curve Tools addon. (N) Panel',
    'description': 'PathFinder - quick search, selection, removal of splines',
    'warning': '', # used for warning icon and text in addons panel
    'wiki_url': '',
    'tracker_url': '',
    'category': 'Curve'}
    
import time
import threading

import gpu
from gpu_extras.batch import batch_for_shader

import bpy
from bpy.props import *
from bpy_extras import object_utils, view3d_utils
from mathutils import  *
from math import  *

from . import Properties
from . import Curves
from . import CurveIntersections
from . import Util
from . import Surfaces
from . import Math

def get_bezier_points(spline, matrix_world):
    point_list = []
    len_bezier_points = len(spline.bezier_points)
    if len_bezier_points > 1:
        for i in range(0, len_bezier_points - 1):
            point_list.extend([matrix_world @ spline.bezier_points[i].co])
            for t in range(0, 100, 2):
                h = Math.subdivide_cubic_bezier(spline.bezier_points[i].co,
                                           spline.bezier_points[i].handle_right,
                                           spline.bezier_points[i + 1].handle_left,
                                           spline.bezier_points[i + 1].co,
                                           t/100)
                point_list.extend([matrix_world @ h[2]])
        if spline.use_cyclic_u and len_bezier_points > 2:
            point_list.extend([matrix_world @ spline.bezier_points[len_bezier_points - 1].co])
            for t in range(0, 100, 2):
                h = Math.subdivide_cubic_bezier(spline.bezier_points[len_bezier_points - 1].co,
                                           spline.bezier_points[len_bezier_points - 1].handle_right,
                                           spline.bezier_points[0].handle_left,
                                           spline.bezier_points[0].co,
                                           t/100)
                point_list.extend([matrix_world @ h[2]])
            point_list.extend([matrix_world @ spline.bezier_points[0].co])

    return point_list
        
def get_points(spline, matrix_world):
    point_list = []
    len_points = len(spline.points)
    if len_points > 1:
        for i in range(0, len_points - 1):
            point_list.extend([matrix_world @ Vector((spline.points[i].co.x, spline.points[i].co.y, spline.points[i].co.z))])
            for t in range(0, 100, 2):
                x = (spline.points[i].co.x + t / 100 * spline.points[i + 1].co.x) / (1 + t / 100)
                y = (spline.points[i].co.y + t / 100 * spline.points[i + 1].co.y) / (1 + t / 100)
                z = (spline.points[i].co.z + t / 100 * spline.points[i + 1].co.z) / (1 + t / 100)
                point_list.extend([matrix_world @ Vector((x, y, z))])
        if spline.use_cyclic_u and len_points > 2:
            point_list.extend([matrix_world @ Vector((spline.points[len_points - 1].co.x, spline.points[len_points - 1].co.y, spline.points[len_points - 1].co.z))])
            for t in range(0, 100, 2):
                x = (spline.points[len_points - 1].co.x + t / 100 * spline.points[0].co.x) / (1 + t / 100)
                y = (spline.points[len_points - 1].co.y + t / 100 * spline.points[0].co.y) / (1 + t / 100)
                z = (spline.points[len_points - 1].co.z + t / 100 * spline.points[0].co.z) / (1 + t / 100)
                point_list.extend(matrix_world @ Vector((x, y, z)))
            point_list.extend([matrix_world @ Vector((spline.points[0].co.x, spline.points[0].co.y, spline.points[0].co.z))])
    
    return point_list

def draw_bezier_points(self, context, spline, matrix_world, path_color):
    
    points = get_bezier_points(spline, matrix_world)
    
    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'POINTS', {"pos": points})
    
    shader.bind()
    shader.uniform_float("color", path_color)
    batch.draw(shader)
    
def draw_points(self, context, spline, matrix_world, path_color):
    
    points = get_points(spline, matrix_world)
    
    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'POINTS', {"pos": points})
    
    shader.bind()
    shader.uniform_float("color", path_color)
    batch.draw(shader)

def click(self, context, event):
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.context.view_layer.update()
    for object in context.selected_objects:
        matrix_world = object.matrix_world
        if object.type == 'CURVE':
            curvedata = object.data
            
            radius = bpy.context.scene.curvetools.PathFinderRadius
            
            for spline in curvedata.splines:
                for bezier_point in spline.bezier_points:
                    factor = 0
                    co = matrix_world @ bezier_point.co
                    if co.x > (self.location3D.x - radius):
                        factor += 1
                    if co.x < (self.location3D.x + radius):
                        factor += 1
                    if co.y > (self.location3D.y - radius):
                        factor += 1
                    if co.y < (self.location3D.y + radius):
                        factor += 1
                    if co.z > (self.location3D.z - radius):
                        factor += 1
                    if co.z < (self.location3D.z + radius):
                        factor += 1
                    
                    if factor == 6:
                        
                        args = (self, context, spline, matrix_world, self.path_color)
                        
                        self.handlers.append(bpy.types.SpaceView3D.draw_handler_add(draw_bezier_points, args, 'WINDOW', 'POST_VIEW'))

                        for bezier_point in spline.bezier_points:
                            bezier_point.select_control_point = True
                            bezier_point.select_left_handle = True
                            bezier_point.select_right_handle = True
            
            for spline in curvedata.splines:
                for point in spline.points:
                    factor = 0
                    co = matrix_world @ Vector((point.co.x, point.co.y, point.co.z))
                    if co.x > (self.location3D.x - radius):
                        factor += 1
                    if co.x < (self.location3D.x + radius):
                        factor += 1
                    if co.y > (self.location3D.y - radius):
                        factor += 1
                    if co.y < (self.location3D.y + radius):
                        factor += 1
                    if co.z > (self.location3D.z - radius):
                        factor += 1
                    if co.z < (self.location3D.z + radius):
                        factor += 1
                    if factor == 6:
                        
                        args = (self, context, spline, matrix_world, self.path_color)
                        
                        self.handlers.append(bpy.types.SpaceView3D.draw_handler_add(draw_points, args, 'WINDOW', 'POST_VIEW'))
                        
                        for point in spline.points:
                            point.select = True    

class PathFinder(bpy.types.Operator):
    bl_idname = "curvetools2.pathfinder"
    bl_label = "Path Finder"
    bl_description = "Path Finder"
    bl_options = {'REGISTER', 'UNDO'}
    
    x: IntProperty(name="x", description="x")
    y: IntProperty(name="y", description="y")
    location3D: FloatVectorProperty(name = "",
                description = "Start location",
                default = (0.0, 0.0, 0.0),
                subtype = 'XYZ')
                
    handlers = []
    
    def __init__(self):
        self.report({'INFO'}, "ESC or TAB - cancel")

    def __del__(self):
        self.report({'INFO'}, "PathFinder deactivated")
        
    def execute(self, context):
        bpy.ops.object.mode_set(mode = 'EDIT')
        
        # color change in the panel
        self.path_color = bpy.context.scene.curvetools.path_color

    def modal(self, context, event):
        context.area.tag_redraw()
        
        if event.type in {'ESC', 'TAB'}:  # Cancel
            for handler in self.handlers:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
                except:
                    pass
            for handler in self.handlers:
                self.handlers.remove(handler)
            return {'CANCELLED'}
        
        elif event.alt and event.type == 'LEFTMOUSE':
            click(self, context, event)
                                    
        elif event.alt and event.type == 'RIGHTMOUSE':
           click(self, context, event)
            
        elif event.type == 'A':
            for handler in self.handlers:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
                except:
                    pass
            for handler in self.handlers:
                self.handlers.remove(handler)
            bpy.ops.curve.select_all(action='DESELECT')
            
        elif event.type == 'MOUSEMOVE':  # 
            self.x = event.mouse_x
            self.y = event.mouse_y
            region = bpy.context.region
            rv3d = bpy.context.space_data.region_3d
            self.location3D = view3d_utils.region_2d_to_location_3d(
                region,
                rv3d,
                (event.mouse_region_x, event.mouse_region_y),
                (0.0, 0.0, 0.0)
                )       

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.execute(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
        
    @classmethod
    def poll(cls, context):
        return (context.object is not None and
                context.object.type == 'CURVE')

def register():
    bpy.utils.register_class(PathFinder)

def unregister():
    bpy.utils.unregister_class(PathFinder)

if __name__ == "__main__":
    register()
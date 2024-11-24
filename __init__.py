# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
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

# This file is part of the Blender addon originally authored by Joshua Bogart.
# See https://github.com/JoshRBogart/unreal_tools (vertex_animation.py)
# It has been modified by Tensor as of 2024-08-26.
# The original code is licensed under the GPL v3 or later, and so is this modified version.


bl_info = {
    "name": "Sansar Vertex Animation",
    "author": "Tensor",
    "version": (1, 4),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Sansar Tools Tab",
    "description": "A tool for storing per frame vertex data for use in Sansar VAT shader.",
    "warning": "",
    "doc_url": "",
    "category": "Sansar Tools",
}


import bpy
import bmesh
import math
import numpy as np
import mathutils
import sys
from bpy.types import AddonPreferences, Panel
from bpy.props import StringProperty

imageWidthGranularity = 32
imageHeightGranularity = 32


def split_edges_by_normal(obj, angle_threshold=0.1, triangulate=True):
    
    # Store selection and then deselect everything
    selected_objects = bpy.context.selected_objects[:]
    active_object = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')

    # Ensure the object is in object mode
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Create a BMesh representation of the mesh
    bm = bmesh.from_edit_mesh(obj.data)
    
    # Convert the angle threshold to radians
    angle_threshold_rad = angle_threshold * (3.14159 / 180.0)
    
    # Ensure the normals are updated
    bm.normal_update()
    
    # Deselect all edges initially
    for edge in bm.edges:
        edge.select = False
    
    # We also need the mesh (object mode) because in bmesh we don't have the 
    # splitted normals available, see
    # https://blender.stackexchange.com/questions/249611/how-to-get-split-normal-of-selected-vertex-in-python

    me = obj.data

    # calc_normals_split was removed in Blender 4.2, see
    # https://developer.blender.org/docs/release_notes/4.1/python_api/#mesh    
    if bpy.app.version_string[0]=='4':
        getNormal = lambda idx : me.corner_normals[idx].vector
    else:
        me.calc_normals_split()
        getNormal = lambda idx : me.loops[idx].normal
        
    # Check if bpy.app.version_string starts with "4", if so
    # then don't use me.calc_normals_split() and below
    # replace me.loops[..].normal by
    # me.corner_normals[..].vector
    

    # Iterate over all vertices
    for edge in bm.edges:
        if len(edge.link_faces) == 2:  # Only consider edges shared by two faces
            # Get the loops corresponding to the edge for each face
            face1 = edge.link_faces[0]
            face2 = edge.link_faces[1]

            issharp = False

            for vert in edge.verts:

                # Find the loop corresponding to the edge in both faces
                loop1 = None
                loop2 = None
                
                for loop in face1.loops:
                    if loop.vert.index == vert.index:
                        loop1 = loop
                        break
                
                for loop in face2.loops:    
                    if loop.vert.index == vert.index:
                        loop2 = loop
                        break

                # Compare the normals of the two loops
                
                normal1 = getNormal(loop1.index) # me.loops[loop1.index].normal # calc_normal()
                normal2 = getNormal(loop2.index) # me.loops[loop2.index].normal # calc_normal()

                if normal1.angle(normal2) > 1e-5:  # Small threshold for float precision
                    issharp = True
                
            if issharp:
                edge.select = True

    # Triangulate the mesh
    bpy.ops.mesh.edge_split(type='EDGE')

    # # Triangulate the mesh
    for elem in bm.faces:
        elem.select = True
    if triangulate:
        bpy.ops.mesh.quads_convert_to_tris()
    
    # Update the mesh and return to object mode
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Restore the selection
    for obj in selected_objects:
        obj.select_set(True)
    if active_object is not None:
        bpy.context.view_layer.objects.active = active_object

def get_per_frame_mesh_data(context, data, objects):
    """Return a list of combined mesh data per frame"""
    meshes = []
    curFrame = context.scene.frame_current
    for i in frame_range(context.scene):
        context.scene.frame_set(i)
        depsgraph = context.evaluated_depsgraph_get()
        bm = bmesh.new()
        for ob in objects:
            eval_object = ob.evaluated_get(depsgraph)
            me = data.meshes.new_from_object(eval_object)
            me.transform(ob.matrix_world)
            bm.from_mesh(me)
            data.meshes.remove(me)
        me = data.meshes.new('frame_{:03d}'.format(i))
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        me.update()
        meshes.append(me)
    context.scene.frame_set(curFrame)
    return meshes


def create_export_mesh_object(context, data, me):
    """Return a mesh object with correct UVs"""
    while len(me.uv_layers) < 2:
        me.uv_layers.new()
    uv_layer = me.uv_layers[1]
    uv_layer.name = "vertex_anim"
    for loop in me.loops:
        vertIdx_LSH = (loop.vertex_index % 2048) - 2048 # Zero is at -2048
        vertIdx_MSH = (loop.vertex_index // 2048) - 2047 # v is flipped in sansar, therefore we need to define zero at -2047 such that it can be encoded as +2047
        uv_layer.data[loop.index].uv = (
            #(loop.vertex_index + 0.5)/len(me.vertices), 128/255
            #(loop.vertex_index + 0.5)/imageWidth, 128/255
            vertIdx_LSH, vertIdx_MSH
        )
    ob = data.objects.new("export_mesh", me)
    context.scene.collection.objects.link(ob)
    return ob


def get_vertex_data(data, meshes, vertex_count, frame_count):
    """Return lists of vertex offsets and normals from a list of mesh data"""
    # meshes[0].calc_normals_split()
    meshes[0].calc_tangents()
    original = meshes[0].vertices
    originalL = meshes[0].loops

    offsets = np.zeros((len(original)*len(meshes)+1, 4))
    normals = np.zeros((len(original)*len(meshes)+1, 4))

    # Write header
    vertex_count_MSH = (vertex_count // 2048) - 2048
    vertex_count_LSH = (vertex_count % 2048) - 2048 
    frame_count_MSH = (frame_count // 2048) - 2048
    frame_count_LSH = (frame_count % 2048) - 2048 

    offsets[0] = (vertex_count_MSH, vertex_count_LSH, frame_count_LSH, 1)
    normals[0] = (vertex_count_MSH, vertex_count_LSH, frame_count_LSH, 1)

    wm = bpy.context.window_manager
    wm.progress_begin(0, vertex_count*frame_count)
    start_of_frame = 1
    for me in meshes:
        # me.calc_normals_split()
        me.calc_tangents()
        for v in me.vertices:
            offset = v.co - original[v.index].co
            offsets[start_of_frame+v.index] = (*offset, 1)


        
        for l in me.loops:
            l0 = originalL[l.index]


            if 1:
                N0 = l0.normal.normalized()
                T0 = l0.tangent.normalized()
                B0 = N0.cross(T0).normalized()
                
                N = l.normal.normalized()
                T = l.tangent.normalized()
                B = N.cross(T).normalized()

                M0 = mathutils.Matrix((N0,T0,B0))
                M = mathutils.Matrix((N,T,B))

                rot = M.inverted() @ M0
                quat = rot.to_quaternion()
            else:
                A = l0.normal
                B = l.normal
                if  A != B:               
                    quat = mathutils.Quaternion((1 + A.dot(B), *A.cross(B))).normalized()
                else:
                    quat = mathutils.Quaternion((1, 0, 0, 0))  


            normals[start_of_frame+l.vertex_index] = (quat.x, quat.y, quat.z, quat.w)

        start_of_frame += len(me.vertices)
        wm.progress_update(start_of_frame)


    offsets = offsets.flatten()
    normals = normals.flatten()
    wm.progress_end()


    # Clean intermediate meshes from data cache
    for me in meshes: 
        if not me.users:
            data.meshes.remove(me)

    return offsets, normals


def frame_range(scene):
    """Return a range object with with scene's frame start, end, and step"""
    return range(scene.frame_start, scene.frame_end+1, scene.frame_step)


def bake_vertex_data(data, offsets, normals, size):
    """Stores vertex offsets and normals in seperate image textures"""
    width, height = size
    offset_texture = data.images.new(
        name="offsets",
        width=width,
        height=height,
        alpha=True,
        float_buffer=True
    )
    normal_texture = data.images.new(
        name="normals",
        width=width,
        height=height,
        alpha=True,
        float_buffer=True
    )
    offset_texture.pixels = offsets
    normal_texture.pixels = normals
    return offset_texture, normal_texture

def DecodeMorton2X(code):
    code = code & 0x55555555
    code = (code | (code >> 1)) & 0x33333333
    code = (code | (code >> 2)) & 0x0F0F0F0F
    code = (code | (code >> 4)) & 0x00FF00FF
    code = (code | (code >> 8)) & 0x0000FFFF
    return code

def DecodeMorton2Y(code):
    code = (code >> 1) & 0x55555555
    code = (code | (code >> 1)) & 0x33333333
    code = (code | (code >> 2)) & 0x0F0F0F0F
    code = (code | (code >> 4)) & 0x00FF00FF
    code = (code | (code >> 8)) & 0x0000FFFF
    return code


def exportImage(my_image, output_path):
    output_path = bpy.path.abspath(output_path)

    image_settings = bpy.context.scene.render.image_settings
    image_settings.file_format = "OPEN_EXR"
    image_settings.color_mode = 'RGBA'  # Set to RGBA
    image_settings.color_depth = '16'
    image_settings.exr_codec = 'ZIP'
    image_settings.view_settings.view_transform = 'Raw'  


    my_image.save_render(output_path) # save to desination

def exportMesh(my_mesh, file_path):
    file_path = bpy.path.abspath(file_path)

    # Store selection and then deselect everything
    selected_objects = bpy.context.selected_objects[:]
    active_object = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')

    # Select mesh for export
    bpy.context.view_layer.objects.active = my_mesh
    my_mesh.select_set(True)

    # Define the export settings
    export_settings = {
        "filepath": file_path,
        "check_existing": False,  # Overwrite existing files
        "filter_glob": "*.fbx",

        "path_mode": 'AUTO',  # Automatically set the path mode
        "embed_textures": False,  # Don't embed textures
        "batch_mode": 'OFF',
        "use_batch_own_dir": True,        
        
        "use_selection": True,  # Export only the selected objects
        # Missing Visible Objects: False
        "use_active_collection": False,
        "object_types": {'MESH', 'ARMATURE'},  # Export only mesh and armature objects
        "use_custom_props": False,  # Export custom properties

        "global_scale": 1.0,
        # Missing Apply Scalings: 'All local'
        "axis_forward": '-Y',  # Forward axis
        "axis_up": 'Z',  # Up axis
        "apply_unit_scale": True,
        "bake_space_transform": False,
        # Missing Apply Transformation: False
        
        # Missing Smoothing: 'Normals Only'
        "use_subsurf": False,  # Apply subdivision surface modifiers
        "use_mesh_modifiers": True,
        "use_mesh_modifiers_render": True,
        "mesh_smooth_type": 'OFF',  # No smooth groups
        "use_mesh_edges": False,
        # Missing Triangulate Faces: False
        "use_tspace": False,
        # Missing Vertex Colors: 'sRGB'
        # Missing Prioritize Active Color: False
        
        "primary_bone_axis": 'Y',
        "secondary_bone_axis": 'X',
        "armature_nodetype": 'NULL',
        "use_armature_deform_only": False,
        "add_leaf_bones": False,
        
        "bake_anim": True,  # Export animations
        "bake_anim_use_all_bones": True,
        "bake_anim_use_nla_strips": False,
        "bake_anim_use_all_actions": False,
        "bake_anim_force_startend_keying": True,
        # Missing Sampling Rate: 1.0
        "bake_anim_simplify_factor": 1.0,  # Keyframe reduction
        "use_metadata": True,
    }

    # Export the selected objects as an FBX file with the specified settings
    bpy.ops.export_scene.fbx(**export_settings)
    
    # Restore the selection
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected_objects:
        obj.select_set(True)
    if active_object is not None:
        bpy.context.view_layer.objects.active = active_object
   
def cleanup(objects):
    # Delete the copied objects
    for obj in objects:
        bpy.context.view_layer.active_layer_collection.collection.objects.unlink(obj)
        bpy.data.objects.remove(obj, do_unlink=True)
    objects.clear()

class OBJECT_OT_ProcessAnimMeshes(bpy.types.Operator):
    """Store combined per frame vertex offsets and normals for all
    selected mesh objects into seperate image textures"""
    bl_idname = "object.process_anim_meshes"
    bl_label = "Start Processing"

    @property
    def allowed_modifiers(self):
        return [
            'ARMATURE', 'CAST', 'CURVE', 'DISPLACE', 'HOOK',
            'LAPLACIANDEFORM', 'LATTICE', 'MESH_DEFORM',
            'SHRINKWRAP', 'SIMPLE_DEFORM', 'SMOOTH',
            'CORRECTIVE_SMOOTH', 'LAPLACIANSMOOTH',
            'SURFACE_DEFORM', 'WARP', 'WAVE',
        ]

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.type == 'MESH' and ob.mode == 'OBJECT'

    def execute(self, context):
        data = bpy.data

        objects = []
        for obj in context.selected_objects:
            obj_copy = obj.copy()  # Create a copy of the object
            obj_copy.data = obj_copy.data.copy()  # Also copy the mesh data (or other data type)
            context.view_layer.active_layer_collection.collection.objects.link(obj_copy)
            split_edges_by_normal(obj_copy)
            objects.append(obj_copy)  # Add the copy to the list


        vertex_count = sum([len(ob.data.vertices) for ob in objects])
        frame_count = len(frame_range(context.scene))

        for ob in objects:
            for mod in ob.modifiers:
                if mod.type not in self.allowed_modifiers:
                    cleanup(objects)  
                    self.report(
                        {'ERROR'},
                        f"Objects with {mod.type.title()} modifiers are not allowed!"
                    )
                    return {'CANCELLED'}  
        if vertex_count > 4096*4095:
            cleanup(objects)  
            self.report(
                {'ERROR'},
                f"Vertex count of {vertex_count :,}, execedes limit of 16,773,120 (after split normals)!"
            )
            return {'CANCELLED'}
        if frame_count > 4096:
            cleanup(objects)  
            self.report(
                {'ERROR'},
                f"Frame count of {frame_count :,}, execedes limit of 4096!"
            )
            return {'CANCELLED'}
        if frame_count*vertex_count+1 > 8192*8192:
            cleanup(objects)  
            self.report(
                {'ERROR'},
                f"Required number of pixels (header+vertex_count*frame_count) would exceed 8k texture limit."
            )
            return {'CANCELLED'}

        # Capture animation in terms of individual meshes
        meshes = get_per_frame_mesh_data(context, data, objects)
        cleanup(objects)    

        # Export mesh of first frame as reference
        if bpy.context.scene.sansar_vat_settings.gen_mesh:
            export_mesh_data = meshes[0].copy()
            export_mesh = create_export_mesh_object(context, data, export_mesh_data)

        # Create VAT as linear array
        offsets, normals = get_vertex_data(data, meshes, vertex_count, frame_count)
        num_elements = len(offsets) // 4  # Total number of pixels

        if bpy.context.scene.sansar_vat_settings.zcurve:
            wm = bpy.context.window_manager
            wm.progress_begin(0,num_elements)

            max_x = max(DecodeMorton2X(idx) for idx in range(num_elements)) + 1 
            max_y = max(DecodeMorton2Y(idx) for idx in range(num_elements)) + 1 

            imageWidth = int(math.ceil(max_x/imageWidthGranularity)*imageWidthGranularity)
            imageHeight = int(math.ceil(max_y/imageHeightGranularity)*imageHeightGranularity)

            offsets_z_curved = np.zeros((imageHeight, imageWidth, 4))  # 2D array to store the values in Z-curve order
            normals_z_curved = np.zeros((imageHeight, imageWidth, 4))  # 2D array to store the values in Z-curve order

            for idx in range(num_elements):
                x = DecodeMorton2X(idx)
                y = DecodeMorton2Y(idx)
                offsets_z_curved[y, x] = offsets[idx * 4: (idx + 1) * 4]
                normals_z_curved[y, x] = normals[idx * 4: (idx + 1) * 4]
                if idx%5000==0:
                    wm.progress_update(idx)
            wm.progress_end()
            
            # Step 4: Flatten the 2D array into a 1D array
            offsets = offsets_z_curved.flatten().tolist()
            normals = normals_z_curved.flatten().tolist()

        else: # Not z-code encoding
            # Remove first pixel (4 entries in array) as we don't need the header pixel 
            offsets = offsets[4:]
            normals = normals[4:]

            imageWidth = vertex_count
            imageHeight = frame_count


        # Write images
        texture_size = imageWidth, imageHeight
        offset_texture, normal_texture = bake_vertex_data(data, offsets, normals, texture_size)
        if bpy.context.scene.sansar_vat_settings.do_file_export:
            exportImage(offset_texture, bpy.context.scene.sansar_vat_settings.export_folder+bpy.context.scene.sansar_vat_settings.export_file+'_map.exr')
            exportImage(normal_texture, bpy.context.scene.sansar_vat_settings.export_folder+bpy.context.scene.sansar_vat_settings.export_file+'_normal.exr')
            if bpy.context.scene.sansar_vat_settings.gen_mesh:
                exportMesh(export_mesh, bpy.context.scene.sansar_vat_settings.export_folder+bpy.context.scene.sansar_vat_settings.export_file+'_mesh.fbx')
            exportTarget = bpy.path.abspath(bpy.context.scene.sansar_vat_settings.export_folder+bpy.context.scene.sansar_vat_settings.export_file)
            exportTarget = exportTarget.replace("\\", "/")+"*"
            self.report({'INFO'}, f"Exported VAT files to {exportTarget}")
            print(f"Exported VAT files to {exportTarget}")

        
        
        return {'FINISHED'}


class VIEW3D_PT_VertexAnimation(bpy.types.Panel):
    """Creates a Panel in 3D Viewport"""
    bl_label = "Sansar VAT"
    bl_idname = "VIEW3D_PT_vertex_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    #bl_category = "Sansar Tools"

    @classmethod
    def get_sidebar_category(cls):
        # Retrieve the custom category name from preferences
        prefs = bpy.context.preferences.addons[__name__].preferences
        return prefs.sidebar_category

    @classmethod
    def register(cls):
        cls.bl_category = cls.get_sidebar_category()

    @classmethod
    def unregister(cls):
        pass

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        scene = context.scene
        #col = layout.column(align=True)
        layout.label(text="Frame Range:")  
        layout.prop(scene, "frame_start", text="Start")
        layout.prop(scene, "frame_end", text="End")
        layout.prop(scene, "frame_step", text="Step")
        
        layout.prop(scene.sansar_vat_settings, "gen_mesh")
        layout.prop(scene.sansar_vat_settings, "zcurve")
        layout.prop(scene.sansar_vat_settings, "do_file_export")
        
        if bpy.context.scene.sansar_vat_settings.do_file_export:
            layout = layout.column(align=True)
            layout.prop(scene.sansar_vat_settings, "export_folder")
            layout.prop(scene.sansar_vat_settings, "export_file")
        
        layout.operator("object.process_anim_meshes")

def update_sidebar_category(self, context):
    bpy.utils.unregister_class(VIEW3D_PT_VertexAnimation)
    VIEW3D_PT_VertexAnimation.bl_category = self.sidebar_category
    bpy.utils.register_class(VIEW3D_PT_VertexAnimation)

class SansarVATAddonPreferences(AddonPreferences):
    bl_idname = __name__

    sidebar_category: StringProperty(
        name="Sidebar Category",
        description="Name of the sidebar category where the panel will appear",
        default="Sansar VAT",
        update=update_sidebar_category    # Save preferences automatically
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "sidebar_category")

    @classmethod
    def register(cls):
        VIEW3D_PT_VertexAnimation.bl_category = "Sansar VAT"

class SansarVATSettings(bpy.types.PropertyGroup):
    export_folder: bpy.props.StringProperty(
        name="Export Path",
        description="Path to an export directory",
        subtype='DIR_PATH',
        default='//export/'
    ) # type: ignore
    export_file: bpy.props.StringProperty(
        name="Filename",
        default="VAT",
    ) # type: ignore
    gen_mesh: bpy.props.BoolProperty(
        name="Generate Mesh",
        default=True,
    ) # type: ignore
    do_file_export: bpy.props.BoolProperty(
        name="Export Files",
        default=True,
    ) # type: ignore
    zcurve: bpy.props.BoolProperty(
        name="Encode Map as Z-Curve",
        default=True,
    ) # type: ignore
    

def register():
    bpy.utils.register_class(SansarVATAddonPreferences)
    bpy.utils.register_class(SansarVATSettings)
    bpy.types.Scene.sansar_vat_settings = bpy.props.PointerProperty(type=SansarVATSettings)
    bpy.utils.register_class(OBJECT_OT_ProcessAnimMeshes)
    bpy.utils.register_class(VIEW3D_PT_VertexAnimation)

def unregister():
    del bpy.types.Scene.sansar_vat_settings
    bpy.utils.unregister_class(SansarVATSettings)
    bpy.utils.unregister_class(OBJECT_OT_ProcessAnimMeshes)
    bpy.utils.unregister_class(VIEW3D_PT_VertexAnimation)
    bpy.utils.unregister_class(SansarVATAddonPreferences)

if __name__ == "__main__":
    register()

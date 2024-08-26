# Sansar-Blender-Tools
Blender Tools for Creating [Sansar](https://sansar.com/) Assets


## Installation
To install the addon, just download the zip file attached to the [latest release](https://github.com/TENS0R/Sansar-Blender-Tools/releases/latest), and install it as a regular blender addon (User Preferences -> Addons -> Install from file).

## Usage
Select one or several animated objects 

## Credits
The tool for extracting vertex animations is based on the [Unreal Tool for Vertex Animation](https://github.com/JoshRBogart/unreal_tools) by Joshua Bogart. It is ported to be used for Sansar and extended by the following features:
 * Storing the vertices and frames in z-order (Morton code) optimized for texture caching in Sansar.
 * Computation of rotation quaternion for updating tangent space and generation of corresponding map in addition to the displacement map.
 * Preprocessing of meshes for splitting sharp edges when vertices have different normals (required for correct update of tangent space).
 * Automatic export of images as exr textures and mesh as fbx.

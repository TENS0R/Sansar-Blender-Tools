# Sansar-Blender-Tools
Blender Tools for Creating [Sansar](https://sansar.com/) Assets


## Installation
To install the addon, just download the zip file attached to the [latest release](https://github.com/TENS0R/Sansar-Blender-Tools/releases/latest), and install it as a regular blender addon (User Preferences -> Addons -> Install from file).

## Usage
The tool is integrated in the sidebar of the 3D Viewport under the Category 'Sansar Tools'.

Select one or several animated objects to be exported and press 'Start Processing' in the Vertex Animation Tab in the Sansar Tools side bar of the 3D view.
Settings (in the sidebar):
 * Frame range: Selection of frame range for export by specifying first and last frame as well as frame step size.
 * Generate mesh: If checked, the mesh to be uploaded to sansar is generated together with the displacement and normal map. If unchecked, only the textures are generated. 
  * Encode Map as Z-Curve: If checked, the generated images store the data in z-order (Morton Code), which is optimized for caching inside Sansar. In addition, the first pixel is used as a header encoding the number of vertices and the number frames. This option is required for generating Sansar assets. If disabled, the images store the data such that the vertices are the columns and the frames as rows of the images.
 * Export files: Export both images and the mesh (if generated) in the specified export path and filename prefix.

## Credits
The tool for extracting vertex animations is based on the [Unreal Tool for Vertex Animation](https://github.com/JoshRBogart/unreal_tools) by Joshua Bogart. It is ported to be used for Sansar and extended by the following features:
 * Storing the vertices and frames in z-order (Morton code) optimized for texture caching in Sansar.
 * Computation of rotation quaternion for updating tangent space and generation of corresponding map in addition to the displacement map.
 * Preprocessing of meshes for splitting sharp edges when vertices have different normals (required for correct update of tangent space).
 * Automatic export of images as exr textures and mesh as fbx.

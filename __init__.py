bl_info = {
    "name": "Live Manga/Webtoon Converter",
    "author": "Grok",
    "version": (7, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Manga",
    "description": "Final tuned version - Saturation 1.0 + Color Ramp black at 0.58",
    "category": "Image",
}

import bpy
import os

# ====================== SAFE INPUT ======================
def get_node(tree, name):
    return tree.nodes.get(name)

def safe_set_input(node, socket_name, value):
    if not node or socket_name not in node.inputs:
        return
    sock = node.inputs[socket_name]
    try:
        if sock.type == 'VECTOR':
            v = float(value)
            sock.default_value = (v, v, v)
        else:
            sock.default_value = float(value)
    except:
        try:
            sock.default_value = float(value)
        except:
            pass

def set_kawahara(node, size=8.0):
    if node:
        safe_set_input(node, "Size", size)
        safe_set_input(node, "Uniformity", 4)
        safe_set_input(node, "Sharpness", 1.0)
        safe_set_input(node, "Eccentricity", 1.0)

# ====================== LIVE UPDATES ======================
def update_color_simplify(self, context):
    set_kawahara(get_node(context.scene.node_tree, "Manga_Color_Kuwahara"), self.manga_color_simplify)

def update_line_smooth(self, context):
    set_kawahara(get_node(context.scene.node_tree, "Manga_Line_Kuwahara"), self.manga_line_smooth)

def update_contrast(self, context):
    node = get_node(context.scene.node_tree, "Manga_Color_Contrast")
    if node and len(node.inputs) > 2:
        node.inputs[2].default_value = self.manga_contrast

def update_saturation(self, context):
    node = get_node(context.scene.node_tree, "Manga_HSV")
    if node:
        node.inputs[1].default_value = 0.5      # Hue
        node.inputs[2].default_value = self.manga_saturation

def update_line_thresh(self, context):
    node = get_node(context.scene.node_tree, "Manga_Line_Ramp")
    if node and len(node.color_ramp.elements) >= 2:
        t = self.manga_line_thresh
        node.color_ramp.elements[0].position = max(0.0, t - 0.1)
        node.color_ramp.elements[1].position = min(1.0, t + 0.05)

# ====================== SETUP ======================
class MANGA_OT_setup_preview(bpy.types.Operator):
    bl_idname = "manga.setup_preview"
    bl_label = "Setup Live Preview"
    bl_description = "Build final manga node tree"

    def execute(self, context):
        scene = context.scene
        input_dir = bpy.path.abspath(scene.manga_input_dir)
        if not os.path.exists(input_dir):
            self.report({'ERROR'}, "Input folder not found")
            return {'CANCELLED'}

        valid = {'.png','.jpg','.jpeg','.bmp','.tif','.tiff'}
        files = sorted([f for f in os.listdir(input_dir) if os.path.splitext(f)[1].lower() in valid])
        if not files:
            self.report({'WARNING'}, "No images found")
            return {'CANCELLED'}

        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.render.use_compositing = True
        scene.use_nodes = True

        tree = scene.node_tree
        tree.nodes.clear()

        # Input
        img_node = tree.nodes.new('CompositorNodeImage')
        img_node.name = "Manga_Image"
        img_node.image = bpy.data.images.load(os.path.join(input_dir, files[0]))
        img_node.location = (-2000, 0)

        # Color Path
        k_color = tree.nodes.new('CompositorNodeKuwahara')
        k_color.name = "Manga_Color_Kuwahara"
        k_color.location = (-1500, 300)
        set_kawahara(k_color, scene.manga_color_simplify)

        contrast = tree.nodes.new('CompositorNodeBrightContrast')
        contrast.name = "Manga_Color_Contrast"
        contrast.location = (-1200, 300)
        contrast.inputs[2].default_value = scene.manga_contrast

        hsv = tree.nodes.new('CompositorNodeHueSat')
        hsv.name = "Manga_HSV"
        hsv.inputs[1].default_value = 0.5      # Hue
        hsv.inputs[2].default_value = scene.manga_saturation
        hsv.location = (-900, 300)

        # Line Path
        k_line = tree.nodes.new('CompositorNodeKuwahara')
        k_line.name = "Manga_Line_Kuwahara"
        k_line.location = (-1600, -300)
        set_kawahara(k_line, scene.manga_line_smooth)

        bw = tree.nodes.new('CompositorNodeRGBToBW')
        bw.location = (-1350, -300)

        sobel = tree.nodes.new('CompositorNodeFilter')
        sobel.filter_type = 'SOBEL'
        sobel.location = (-1100, -300)

        ramp = tree.nodes.new('CompositorNodeValToRGB')
        ramp.name = "Manga_Line_Ramp"
        ramp.location = (-800, -300)
        ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
        ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
        ramp.color_ramp.elements[1].position = 0.58   # Black slider at 0.58 as requested

        # Mix
        mix = tree.nodes.new('CompositorNodeMixRGB')
        mix.name = "Manga_Mix"
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 0.5
        mix.location = (-400, 0)

        composite = tree.nodes.new('CompositorNodeComposite')
        composite.location = (200, 100)

        viewer = tree.nodes.new('CompositorNodeViewer')
        viewer.location = (200, -100)

        # Links
        links = tree.links
        # Color
        links.new(img_node.outputs[0], k_color.inputs[0])
        links.new(k_color.outputs[0], contrast.inputs[0])
        links.new(contrast.outputs[0], hsv.inputs[0])
        links.new(hsv.outputs[0], mix.inputs[1])

        # Lines
        links.new(img_node.outputs[0], k_line.inputs[0])
        links.new(k_line.outputs[0], bw.inputs[0])
        links.new(bw.outputs[0], sobel.inputs[1])      # Fac
        links.new(k_line.outputs[0], sobel.inputs[0])   # Image
        links.new(sobel.outputs[0], ramp.inputs[0])
        links.new(ramp.outputs[0], mix.inputs[2])

        links.new(mix.outputs[0], composite.inputs[0])
        links.new(mix.outputs[0], viewer.inputs[0])

        self.report({'INFO'}, "✅ Setup complete - Saturation 1.0 + Ramp at 0.58")
        return {'FINISHED'}


# ====================== BATCH EXPORT ======================
class MANGA_OT_batch_export(bpy.types.Operator):
    bl_idname = "manga.batch_export"
    bl_label = "Batch Export Manga"
    bl_description = "Process all images"

    def execute(self, context):
        scene = context.scene
        input_dir = bpy.path.abspath(scene.manga_input_dir)
        output_dir = bpy.path.abspath(scene.manga_output_dir)
        os.makedirs(output_dir, exist_ok=True)

        tree = scene.node_tree
        img_node = tree.nodes.get("Manga_Image")
        if not img_node:
            self.report({'ERROR'}, "Run Setup Live Preview first")
            return {'CANCELLED'}

        valid = {'.png','.jpg','.jpeg','.bmp','.tif','.tiff'}
        files = [f for f in os.listdir(input_dir) if os.path.splitext(f)[1].lower() in valid]

        for f in files:
            bl_img = bpy.data.images.load(os.path.join(input_dir, f), check_existing=True)
            img_node.image = bl_img

            scene.render.resolution_x = bl_img.size[0]
            scene.render.resolution_y = bl_img.size[1]
            scene.render.resolution_percentage = 100
            scene.render.filepath = os.path.join(output_dir, os.path.splitext(f)[0] + "_manga.png")
            scene.render.image_settings.file_format = 'PNG'
            scene.render.image_settings.color_mode = 'RGB'

            bpy.context.view_layer.update()
            bpy.ops.render.render(write_still=True)
            bpy.data.images.remove(bl_img)

        self.report({'INFO'}, f"✅ Exported {len(files)} images")
        return {'FINISHED'}


# ====================== UI ======================
class VIEW3D_PT_manga_batch(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Manga'
    bl_label = "Manga / Webtoon Converter"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "manga_input_dir")
        layout.prop(scene, "manga_output_dir")

        layout.separator()
        layout.operator("manga.setup_preview", icon='PLAY')

        layout.separator()
        layout.label(text="Color Settings:")
        box = layout.box()
        box.prop(scene, "manga_color_simplify")
        box.prop(scene, "manga_contrast")
        box.prop(scene, "manga_saturation")

        layout.separator()
        layout.label(text="Line Settings:")
        box = layout.box()
        box.prop(scene, "manga_line_smooth")
        box.prop(scene, "manga_line_thresh")

        layout.separator()
        layout.operator("manga.batch_export", icon='RENDER_ANIMATION')


def register():
    bpy.utils.register_class(MANGA_OT_setup_preview)
    bpy.utils.register_class(MANGA_OT_batch_export)
    bpy.utils.register_class(VIEW3D_PT_manga_batch)

    bpy.types.Scene.manga_input_dir = bpy.props.StringProperty(name="Input Folder", subtype='DIR_PATH')
    bpy.types.Scene.manga_output_dir = bpy.props.StringProperty(name="Output Folder", subtype='DIR_PATH')

    bpy.types.Scene.manga_color_simplify = bpy.props.IntProperty(name="Color Simplify", default=8, min=1, max=30, update=update_color_simplify)
    bpy.types.Scene.manga_contrast = bpy.props.FloatProperty(name="Contrast", default=1.5, min=0.5, max=3.0, update=update_contrast)
    bpy.types.Scene.manga_saturation = bpy.props.FloatProperty(name="Saturation", default=1.0, min=0.0, max=3.0, update=update_saturation)  # Set to 1.0
    bpy.types.Scene.manga_line_smooth = bpy.props.IntProperty(name="Line Smooth", default=8, min=1, max=30, update=update_line_smooth)
    bpy.types.Scene.manga_line_thresh = bpy.props.FloatProperty(name="Line Threshold", default=0.58, min=0.01, max=1.0, update=update_line_thresh)  # Matches ramp

def unregister():
    bpy.utils.unregister_class(MANGA_OT_setup_preview)
    bpy.utils.unregister_class(MANGA_OT_batch_export)
    bpy.utils.unregister_class(VIEW3D_PT_manga_batch)

if __name__ == "__main__":
    register()

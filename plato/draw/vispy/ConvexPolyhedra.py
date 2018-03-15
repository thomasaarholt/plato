import itertools
import numpy as np
from ... import mesh
from .internal import GLPrimitive, GLShapeDecorator
from ... import prims
from ...prims.internal import ShapeAttribute
from vispy import gloo

@GLShapeDecorator
class ConvexPolyhedra(prims.ConvexPolyhedra, GLPrimitive):
    """Holds the vispy state (set of programs) required to draw a set of
    convex polyhedra

    """

    uniforms = ['camera', 'ambientLight', 'diffuseLight', 'rotation',
                'translation', 'outline', 'light_levels']

    attributes = ['position', 'orientation', 'color', 'image', 'face_center',
                  'normal']

    shaders = {}

    shaders['vertex'] = """
       uniform mat4 camera;
       uniform vec4 rotation;
       uniform vec3 translation;
       uniform float outline;

       attribute vec4 orientation;
       attribute vec4 color;
       attribute vec3 position;
       attribute vec3 normal;
       attribute vec3 image;
       attribute vec3 face_center;

       varying vec4 v_color;
       varying vec3 v_normal;
       varying vec3 v_position;
       varying float v_depth;

       vec3 rotate(vec3 point, vec4 quat)
       {
           vec3 result = (quat.x*quat.x - dot(quat.yzw, quat.yzw))*point;
           result += 2.0*quat.x*cross(quat.yzw, point);
           result += 2.0*dot(quat.yzw, point)*quat.yzw;
           return result;
       }

       vec4 quatquat(vec4 a, vec4 b)
       {
           float real = a.x*b.x - dot(a.yzw, b.yzw);
           vec3 imag = a.x*b.yzw + b.x*a.yzw + cross(a.yzw, b.yzw);
           return vec4(real, imag);
       }

       void main()
       {
           vec3 rot_normal = rotate(normal, quatquat(rotation, orientation));
           float local_scale = 1.0;
           if(rot_normal.z > 0.0)
               local_scale -= outline;

           vec3 scaled_image = face_center + (image - face_center)*local_scale;

           vec3 vertexPos = position + rotate(scaled_image, orientation);
           vertexPos = rotate(vertexPos, rotation) + translation;
           vec4 screenPosition = camera * vec4(vertexPos, 1.0);

           // transform to screen coordinates
           gl_Position = screenPosition;
           v_color = color;
           v_normal = rot_normal;
           v_position = vertexPos;
           v_depth = vertexPos.z;
       }
       """

    shaders['fragment'] = """
       varying vec4 v_color;
       varying vec3 v_normal;
       varying float v_depth;

       // base light level
       uniform float ambientLight;
       // (x, y, z) direction*intensity
       uniform vec3 diffuseLight;
       uniform float u_pass;
       uniform float light_levels;

       void main()
       {
           float light = max(0.0, -dot(v_normal, diffuseLight));
           light += ambientLight;

           light *= float(v_normal.z > 0.0);

           if(light_levels > 0.0)
           {
               light *= light_levels;
               light = floor(light);
               light /= light_levels;
           }

           #ifdef IS_TRANSPARENT
           float z = abs(v_depth);
           float alpha = v_color.a;
           //float weight = pow(alpha, 1.0f) * clamp(0.002f/(1e-5f + pow(z/200.0f, 4.0f)), 1e-2, 3e3);
           float weight = alpha * max(3.0*pow(10.0, 3.0)*pow((1-(gl_FragCoord.z)), 3.0f), 1e-2);

           if( u_pass < 0.5 )
           {
              gl_FragColor = vec4(v_color.rgb * alpha * light, alpha) * weight;
           }
           else
           {
              gl_FragColor = vec4(alpha);
           }
           #else
           gl_FragColor = vec4(v_color.xyz*light, v_color.w);
           #endif
       }
       """

    shaders['fragment_plane'] = """
       varying vec3 v_normal;
       varying vec3 v_position;

       uniform mat4 camera;
       // base light level
       uniform float ambientLight;
       // (x, y, z) direction*intensity
       uniform vec3 diffuseLight;
       uniform float renderPositions = 0.0;

       void main()
       {
           if(renderPositions > 0.5)
               gl_FragColor = vec4(gl_FragCoord.xyz, 1.0);
           else // Store the plane equation as a color
               gl_FragColor = vec4(v_normal, dot(v_normal, v_position.xyz));
       }
       """

    _vertex_attribute_names = ['position', 'orientation', 'color', 'image', 'normal', 'face_center']

    _GL_UNIFORMS = list(itertools.starmap(ShapeAttribute, [
        ('camera', np.float32, np.eye(4), 2,
         '4x4 Camera matrix for world projection'),
        ('ambientLight', np.float32, .25, 0,
         'Ambient (minimum) light level for all surfaces'),
        ('diffuseLight', np.float32, (.5, .5, .5), 1,
         'Diffuse light direction*magnitude'),
        ('rotation', np.float32, (1, 0, 0, 0), 1,
         'Rotation to be applied to each scene as a quaternion'),
        ('translation', np.float32, (0, 0, 0), 1,
         'Translation to be applied to the scene'),
        ('outline', np.float32, 0, 0,
         'Outline width for shapes'),
        ('light_levels', np.float32, 0, 0,
         'Number of light levels to quantize to (0: disable)')
        ]))

    def __init__(self, *args, **kwargs):
        GLPrimitive.__init__(self)
        prims.ConvexPolyhedra.__init__(self, *args, **kwargs)

    def update_arrays(self):
        if 'vertices' in self._dirty_attributes:
            vertices = self.vertices
            if len(vertices) < 4:
                vertices = np.concatenate([vertices,
                    [(-1, -1, -1), (1, 1, -1), (1, -1, 1), (-1, 1, 1)]], axis=0)
            (image, normal, indices, face_center) = mesh.convexPolyhedronMesh(vertices)
            self._gl_attributes['image'] = image
            self._gl_attributes['normal'] = normal
            self._gl_attributes['indices'] = indices
            self._gl_attributes['face_center'] = face_center

        try:
            for name in self._dirty_attributes:
                if name == 'vertices':
                    for quantity in ['image', 'normal', 'indices', 'face_center']:
                        self._gl_vertex_arrays[quantity][:] = self._gl_attributes[quantity][np.newaxis]
                        self._dirty_vertex_attribs.add(quantity)
                else:
                    self._gl_vertex_arrays[name][:] = self._attributes[name]
                    self._dirty_vertex_attribs.add(name)
        except (ValueError, KeyError):
            vertex_arrays = mesh.unfoldProperties(
                [self.positions, self.orientations, self.colors],
                [self._gl_attributes[name] for name in ['image', 'normal', 'face_center']])

            unfolded_shape = vertex_arrays[0].shape[:-1]
            indices = (np.arange(unfolded_shape[0])[:, np.newaxis, np.newaxis]*unfolded_shape[1] +
                       self._gl_attributes['indices'])
            indices = indices.reshape((-1, 3))

            indexDtype = np.uint16 if self._webgl else np.uint32
            maxIndex = 2**16 - 1 if self._webgl else 2**32 - 1
            self._gl_vertex_arrays['indices'] = [(scat, gloo.IndexBuffer(np.ascontiguousarray(ind, dtype=indexDtype)))
                for (scat, ind) in mesh.splitChunks(indices, maxIndex=maxIndex)]

            for (name, value) in zip(self._vertex_attribute_names, vertex_arrays):
                self._gl_vertex_arrays[name] = value
                self._dirty_vertex_attribs.add(name)

        self._dirty_attributes.clear()

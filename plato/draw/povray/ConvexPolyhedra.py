import itertools
import numpy as np
from ... import draw
from ... import mesh as pmesh
from ... import geometry
from ... import math as pmath
from ..internal import ShapeAttribute

class ConvexPolyhedra(draw.ConvexPolyhedra):
    __doc__ = draw.ConvexPolyhedra.__doc__

    _ATTRIBUTES = draw.ConvexPolyhedra._ATTRIBUTES

    _ATTRIBUTES.extend(list(itertools.starmap(ShapeAttribute, [
        ('outline', np.float32, 1e-2, 1, 'Outline thickness')
    ])))

    def render(self, rotation=(1, 0, 0, 0), name_suffix='', **kwargs):
        rotation = np.asarray(rotation)

        lines = []

        if self.outline:
            diameter = np.sqrt(np.max(np.sum(self.vertices**2, axis=-1)))
            outline = self.outline*diameter
            decomp = geometry.convexDecomposition(self.vertices)
            edges = ['cylinder {{<{0[0]},{0[1]},{0[2]}> '
                     '<{1[0]},{1[1]},{1[2]}> {2}}}'.format(
                         decomp.vertices[i], decomp.vertices[j],
                         np.asscalar(outline/2))
                     for (i, j) in decomp.edges]
            spheres = ['sphere {{<{0[0]},{0[1]},{0[2]}> {1}}}'.format(
                v, np.asscalar(outline/2)) for v in decomp.vertices]
            shapeName = 'spoly{}'.format(name_suffix)
            shapedef = '#declare {} = union {{\n{}\n}}'.format(
                shapeName, '\n'.join(elt for elt in edges + spheres))
            lines.append(shapedef)

            qs = pmath.quatquat(rotation[np.newaxis, :],
                                self.orientations.copy())
            rotmat = np.array([[1 - 2*qs[:, 2]**2 - 2*qs[:, 3]**2,
                                2*(qs[:, 1]*qs[:, 2] - qs[:, 3]*qs[:, 0]),
                                2*(qs[:, 1]*qs[:, 3] + qs[:, 2]*qs[:, 0])],
                               [2*(qs[:, 1]*qs[:, 2] + qs[:, 3]*qs[:, 0]),
                                1 - 2*qs[:, 1]**2 - 2*qs[:, 3]**2,
                                2*(qs[:, 2]*qs[:, 3] - qs[:, 1]*qs[:, 0])],
                               [2*(qs[:, 1]*qs[:, 3] - qs[:, 2]*qs[:, 0]),
                                2*(qs[:, 1]*qs[:, 0] + qs[:, 2]*qs[:, 3]),
                                1 - 2*qs[:, 1]**2 - 2*qs[:, 2]**2]])
            rotmat = rotmat.transpose([2, 0, 1]).reshape((-1, 9))

            positions = pmath.quatrot(rotation[np.newaxis, :], self.positions)

            for (p, m) in zip(positions, rotmat):
                args = [shapeName] + m.tolist() + p.tolist()
                lines.append('object {{{} matrix <{},{},{},{},{},{},{},{},{},'
                             '{},{},{}> pigment {{color <{},{},{}>}}}}'.format(
                                 *tuple(args) + (0,0,0)))

        mesh = pmesh.convexPolyhedronMesh(self.vertices)
        meshStr = 'mesh2 {{vertex_vectors {{{} {}}} ' \
                  'face_indices {{{} {}}}}}'.format(
            len(mesh.image), ' '.join('<{},{},{}>'.format(*v)
                                      for v in mesh.image),
            len(mesh.indices), ' '.join('<{},{},{}>'.format(*v)
                                        for v in mesh.indices))
        shapeName = 'poly{}'.format(name_suffix)
        shapedef = '#declare {} = {}'.format(shapeName, meshStr)
        lines.append(shapedef)

        qs = pmath.quatquat(rotation[np.newaxis, :], self.orientations.copy())
        rotmat = np.array([[1 - 2*qs[:, 2]**2 - 2*qs[:, 3]**2,
                            2*(qs[:, 1]*qs[:, 2] - qs[:, 3]*qs[:, 0]),
                            2*(qs[:, 1]*qs[:, 3] + qs[:, 2]*qs[:, 0])],
                           [2*(qs[:, 1]*qs[:, 2] + qs[:, 3]*qs[:, 0]),
                            1 - 2*qs[:, 1]**2 - 2*qs[:, 3]**2,
                            2*(qs[:, 2]*qs[:, 3] - qs[:, 1]*qs[:, 0])],
                           [2*(qs[:, 1]*qs[:, 3] - qs[:, 2]*qs[:, 0]),
                            2*(qs[:, 1]*qs[:, 0] + qs[:, 2]*qs[:, 3]),
                            1 - 2*qs[:, 1]**2 - 2*qs[:, 2]**2]])
        rotmat = rotmat.transpose([2, 0, 1]).reshape((-1, 9))

        # invert positions to go into left-handed coordinate system
        positions = pmath.quatrot(rotation[np.newaxis, :], self.positions)

        for (p, m, (r, g, b), a) in zip(positions, rotmat, self.colors[:, :3],
                                        1 - self.colors[:, 3]):
            args = [shapeName] + m.tolist() + p.tolist() + [r, g, b, a]
            lines.append('object {{{} matrix <{},{},{},{},{},{},{},{},{},'
                         '{},{},{}> pigment {{color <{},{},{}> transmit '
                         '{}}}}}'.format(*args))

        return lines
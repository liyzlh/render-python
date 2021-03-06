#!/usr/bin/env python
'''
handling mpicbg transforms in python

Currently only implemented to facilitate Affine, Polynomial2D,
    and LensCorrection used in Khaled Khairy's EM aligner workflow
'''
import json
import logging
from collections import Iterable
import numpy as np
from .errors import ConversionError, EstimationError, RenderError
from .utils import NullHandler

logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())

try:
    from scipy.linalg import svd, LinAlgError
except ImportError as e:
    logger.info(e)
    logger.info('scipy-based linalg may or may not lead '
                'to better parameter fitting')
    from numpy.linalg import svd
    from numpy.linalg.linalg import LinAlgError


class TransformList:
    def __init__(self, tforms=None, transformId=None, json=None):
        if json is not None:
            self.from_dict(json)
        else:
            if tforms is None:
                self.tforms = []
            else:
                if not isinstance(tforms, list):
                    raise RenderError(
                        'unexpected type {} for transforms!'.format(
                            type(tforms)))
                self.tforms = tforms
            self.transformId = transformId

    def to_dict(self):
        d = {}
        d['type'] = 'list'
        d['specList'] = [tform.to_dict() for tform in self.tforms]
        if self.transformId is not None:
            d['id'] = self.transformId
        return d

    def to_json(self):
        return json.dumps(self.to_dict())

    def from_dict(self, d):
        self.tforms = []
        if d is not None:
            self.transformId = d.get('id')
            for td in d['specList']:
                self.tforms.append(load_transform_json(td))
        return self.tforms


def load_transform_json(d, default_type='leaf'):
    handle_load_tform = {'leaf': load_leaf_json,
                         'list': lambda x: TransformList(json=x),
                         'ref': lambda x: ReferenceTransform(json=x),
                         'interpolated':
                             lambda x: InterpolatedTransform(json=x)}
    try:
        return handle_load_tform[d.get('type', default_type)](d)
    except KeyError as e:
        raise RenderError('Unknown Transform Type {}'.format(e))


def load_leaf_json(d):
    handle_load_leaf = {
        AffineModel.className: lambda x: AffineModel(json=x),
        Polynomial2DTransform.className:
            lambda x: Polynomial2DTransform(json=x),
        TranslationModel.className: lambda x: TranslationModel(json=x),
        RigidModel.className: lambda x: RigidModel(json=x),
        SimilarityModel.className: lambda x: SimilarityModel(json=x)}

    tform_type = d.get('type', 'leaf')
    if tform_type != 'leaf':
        raise RenderError(
            'Unexpected or unknown Transform Type {}'.format(tform_type))
    tform_class = d['className']
    try:
        return handle_load_leaf[tform_class](d)
    except KeyError as e:
        logger.info('Leaf transform class {} not defined in '
                    'transform module, using generic'.format(e))
        return Transform(json=d)


class InterpolatedTransform:
    '''
    Transform spec defined by linear interpolation of two other transform specs
    inputs:
        a -- transform spec at minimum weight
        b -- transform spec at maximum weight
        lambda_ -- float value (0.-1.) which defines evaluation of the
            linear interpolation between a (at 0) and b (at 1)
    '''
    def __init__(self, a=None, b=None, lambda_=None, json=None):
        if json is not None:
            self.from_dict(json)
        else:
            self.a = a
            self.b = b
            self.lambda_ = lambda_

    def to_dict(self):
        return dict(self)

    def from_dict(self, d):
        self.a = load_transform_json(d['a'])
        self.b = load_transform_json(d['b'])
        self.lambda_ = d['lambda']

    def __iter__(self):
        return iter([('type', 'interpolated'),
                     ('a', self.a.to_dict()),
                     ('b', self.b.to_dict()),
                     ('lambda', self.lambda_)])


class ReferenceTransform:
    def __init__(self, refId=None, json=None):
        if json is not None:
            self.from_dict(json)
        else:
            self.refId = refId

    def to_dict(self):
        d = {}
        d['type'] = 'ref'
        d['refId'] = self.refId
        return d

    def from_dict(self, d):
        self.refId = d['refId']

    def __str__(self):
        return 'ReferenceTransform(%s)' % self.refId

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        return iter([('type', 'ref'), ('refId', self.refId)])


class Transform(object):
    def __init__(self, className=None, dataString=None,
                 transformId=None, json=None):
        if json is not None:
            self.from_dict(json)
        else:
            self.className = className
            self.dataString = dataString
            self.transformId = transformId

    def to_dict(self):
        d = {}
        d['type'] = 'leaf'
        d['className'] = self.className
        d['dataString'] = self.dataString
        if self.transformId is not None:
            d['transformId'] = self.transformId
        return d

    def from_dict(self, d):
        self.className = d['className']
        self.transformId = d.get('transformId', None)
        self._process_dataString(d['dataString'])

    def _process_dataString(self, datastring):
        self.dataString = datastring

    def __str__(self):
        return 'className:%s\ndataString:%s' % (
            self.className, self.dataString)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.__str__() == other.__str__()

    def __hash__(self):
        return hash((self.__str__()))


class AffineModel(Transform):
    className = 'mpicbg.trakem2.transform.AffineModel2D'

    def __init__(self, M00=1.0, M01=0.0, M10=0.0, M11=1.0, B0=0.0, B1=0.0,
                 transformId=None, json=None):
        if json is not None:
            self.from_dict(json)
        else:
            self.M00 = M00
            self.M01 = M01
            self.M10 = M10
            self.M11 = M11
            self.B0 = B0
            self.B1 = B1
            self.className = 'mpicbg.trakem2.transform.AffineModel2D'
            self.load_M()
            self.transformId = transformId

    @property
    def dataString(self):
        return "%.10f %.10f %.10f %.10f %.10f %.10f" % (
            self.M[0, 0], self.M[1, 0], self.M[0, 1],
            self.M[1, 1], self.M[0, 2], self.M[1, 2])

    def _process_dataString(self, datastring):
        '''
        generate datastring and param attributes from datastring
        '''
        dsList = datastring.split()
        self.M00 = float(dsList[0])
        self.M10 = float(dsList[1])
        self.M01 = float(dsList[2])
        self.M11 = float(dsList[3])
        self.B0 = float(dsList[4])
        self.B1 = float(dsList[5])
        self.load_M()

    def load_M(self):
        self.M = np.identity(3, np.double)
        self.M[0, 0] = self.M00
        self.M[0, 1] = self.M01
        self.M[1, 0] = self.M10
        self.M[1, 1] = self.M11
        self.M[0, 2] = self.B0
        self.M[1, 2] = self.B1

    @staticmethod
    def fit(A, B):
        if not all([A.shape[0] == B.shape[0], A.shape[1] == B.shape[1] == 2]):
            raise EstimationError(
                'shape mismatch! A shape: {}, B shape {}'.format(
                    A.shape, B.shape))

        N = A.shape[0]  # total points

        M = np.zeros((2 * N, 6))
        Y = np.zeros((2 * N, 1))
        for i in range(N):
            M[2 * i, :] = [A[i, 0], A[i, 1], 0, 0, 1, 0]
            M[2 * i + 1, :] = [0, 0, A[i, 0], A[i, 1], 0, 1]
            Y[2 * i] = B[i, 0]
            Y[2 * i + 1] = B[i, 1]

        (Tvec, residuals, rank, s) = np.linalg.lstsq(M, Y)
        return Tvec

    def estimate(self, A, B, return_params=True, **kwargs):
        Tvec = self.fit(A, B, **kwargs)
        self.M00 = Tvec[0, 0]
        self.M10 = Tvec[2, 0]
        self.M01 = Tvec[1, 0]
        self.M11 = Tvec[3, 0]
        self.B0 = Tvec[4, 0]
        self.B1 = Tvec[5, 0]
        self.load_M()
        if return_params:
            return self.M

    def concatenate(self, model):
        '''
        concatenate a model to this model -- ported from trakEM2 below:
            final double a00 = m00 * model.m00 + m01 * model.m10;
            final double a01 = m00 * model.m01 + m01 * model.m11;
            final double a02 = m00 * model.m02 + m01 * model.m12 + m02;

            final double a10 = m10 * model.m00 + m11 * model.m10;
            final double a11 = m10 * model.m01 + m11 * model.m11;
            final double a12 = m10 * model.m02 + m11 * model.m12 + m12;
        '''
        a00 = self.M[0, 0] * model.M[0, 0] + self.M[0, 1] * model.M[1, 0]
        a01 = self.M[0, 0] * model.M[0, 1] + self.M[0, 1] * model.M[1, 1]
        a02 = (self.M[0, 0] * model.M[0, 2] + self.M[0, 1] * model.M[1, 2] +
               self.M[0, 2])

        a10 = self.M[1, 0] * model.M[0, 0] + self.M[1, 1] * model.M[1, 0]
        a11 = self.M[1, 0] * model.M[0, 1] + self.M[1, 1] * model.M[1, 1]
        a12 = (self.M[1, 0] * model.M[0, 2] + self.M[1, 1] * model.M[1, 2] +
               self.M[1, 2])

        newmodel = AffineModel(a00, a01, a10, a11, a02, a12)
        return newmodel

    def invert(self):
        inv_M = np.linalg.inv(self.M)
        Ai = AffineModel(inv_M[0, 0], inv_M[0, 1], inv_M[1, 0],
                         inv_M[1, 1], inv_M[0, 2], inv_M[1, 2])
        return Ai

    @staticmethod
    def convert_to_point_vector(points):
        Np = points.shape[0]
        onevec = np.ones((Np, 1), np.double)

        if points.shape[1] != 2:
            raise ConversionError('Points must be of shape (:, 2) '
                                  '-- got {}'.format(points.shape))
        Nd = 2
        points = np.concatenate((points, onevec), axis=1)
        return points, Nd

    @staticmethod
    def convert_points_vector_to_array(points, Nd):
        points = points[:, 0:Nd] / np.tile(points[:, 2], (Nd, 1)).T
        return points

    def tform(self, points):
        points, Nd = self.convert_to_point_vector(points)
        pt = np.dot(self.M, points.T).T
        return self.convert_points_vector_to_array(pt, Nd)

    def inverse_tform(self, points):
        points, Nd = self.convert_to_point_vector(points)
        pt = np.dot(np.linalg.inv(self.M), points.T).T
        return self.convert_points_vector_to_array(pt, Nd)

    @property
    def scale(self):
        '''tuple of scale for x, y'''
        return tuple([np.sqrt(sum([i ** 2 for i in self.M[:, j]]))
                      for j in range(self.M.shape[1])])[:2]

    @property
    def shear(self):
        '''counter-clockwise shear angle'''
        return np.arctan2(-self.M[0, 1], self.M[1, 1]) - self.rotation

    @property
    def translation(self):
        '''tuple of translation in x, y'''
        return tuple(self.M[:2, 2])

    @property
    def rotation(self):
        '''counter-clockwise rotation'''
        return np.arctan2(self.M[1, 0], self.M[0, 0])

    def __str__(self):
        return "M=[[%f,%f],[%f,%f]] B=[%f,%f]" % (
            self.M[0, 0], self.M[0, 1], self.M[1, 0],
            self.M[1, 1], self.M[0, 2], self.M[1, 2])


class TranslationModel(AffineModel):
    className = 'mpicbg.trakem2.transform.TranslationModel2D'

    def __init__(self, *args, **kwargs):
        super(TranslationModel, self).__init__(*args, **kwargs)
        # raise NotImplementedError(
        #     'TranslationModel not implemented. please use Affine')

    def _process_dataString(self, dataString):
        '''expected dataString is "tx ty"'''
        tx, ty = map(float(dataString.split(' ')))
        self.B0 = tx
        self.B1 = ty
        self.load_M()

    @staticmethod
    def fit(src, dst):
        t = dst.mean(axis=0) - src.mean(axis=0)
        T = np.eye(3)
        T[:2, 2] = t
        return T

    def estimate(self, src, dst, return_params=True):
        self.M = self.fit(src, dst)
        if return_params:
            return self.M


class RigidModel(AffineModel):
    className = 'mpicbg.trakem2.transform.RigidModel2D'

    def __init__(self, *args, **kwargs):
        super(RigidModel, self).__init__(*args, **kwargs)
        # raise NotImplementedError(
        #     'RigidModel not implemented. please use Affine')

    def _process_dataString(self, dataString):
        '''expected datastring is "theta tx ty"'''
        theta, tx, ty = map(float(dataString.split(' ')))
        self.M00 = np.cos(theta)
        self.M01 = -np.sin(theta)
        self.M10 = np.sin(theta)
        self.M11 = np.sin(theta)
        self.B0 = tx
        self.B1 = ty
        self.load_M()

    @staticmethod
    def fit(src, dst, rigid=True, **kwargs):
        '''
        Umeyama estimation of similarity transformation
        '''
        # TODO shape assertion
        num, dim = src.shape
        src_cld = src - src.mean(axis=0)
        dst_cld = dst - dst.mean(axis=0)
        A = np.dot(dst_cld.T, src_cld) / num
        d = np.ones((dim, ), dtype=np.double)
        if np.linalg.det(A) < 0:
            d[dim - 1] = -1
        T = np.eye(dim + 1, dtype=np.double)

        rank = np.linalg.matrix_rank(A)
        if rank == 0:
            raise EstimationError('zero rank matrix A unacceptable -- '
                                  'likely poorly conditioned')

        U, S, V = svd(A)

        if rank == dim - 1:
            if np.linalg.det(U) * np.linalg.det(V) > 0:
                T[:dim, :dim] = np.dot(U, V)
            else:
                s = d[dim - 1]
                d[dim - 1] = -1
                T[:dim, :dim] = np.dot(U, np.dot(np.diag(d), V))
                d[dim - 1] = s
        else:
            T[:dim, :dim] = np.dot(U, np.dot(np.diag(d), V.T))

        fit_scale = (1.0 if rigid else
                     1.0 / src_cld.var(axis=0).sum() * np.dot(S, d))

        T[:dim, dim] = dst.mean(axis=0) - fit_scale * np.dot(
            T[:dim, :dim], src.mean(axis=0).T)
        T[:dim, :dim] *= fit_scale
        return T

    def estimate(self, A, B, return_params=True, **kwargs):
        self.M = self.fit(A, B, **kwargs)
        if return_params:
            return self.M


class SimilarityModel(RigidModel):
    className = 'mpicbg.trakem2.transform.SimilarityModel2D'

    def __init__(self, *args, **kwargs):
        super(SimilarityModel, self).__init__(*args, **kwargs)
        # raise NotImplementedError(
        #     'SimilarityModel not implemented. please use Affine')

    def _process_dataString(self, dataString):
        '''expected datastring is "s theta tx ty"'''
        s, theta, tx, ty = map(float(dataString.split(' ')))
        self.M00 = s * np.cos(theta)
        self.M01 = -s * np.sin(theta)
        self.M10 = s * np.sin(theta)
        self.M11 = s * np.sin(theta)
        self.B0 = tx
        self.B1 = ty
        self.load_M()

    @staticmethod
    def fit(src, dst, rigid=False, **kwargs):
        return RigidModel.fit(src, dst, rigid=rigid)

    # def estimate(self, src, dst, **kwargs):
    #     super(SimilarityModel, self).estimate(src, dst, rigid=False, **kwargs)


class Polynomial2DTransform(Transform):
    '''
    Polynomial2DTransform implemented as in skimage
    Polynomial2DTransform(dataString=None, src=None, dst=None, order=2,
                 force_polynomial=True, params=None, identity=False,
                 json=None)
    This provides 5 different ways to initialize the transform which are
    mutually exclusive and applied in the following order.

    1st
    json = a json dictonary representation of the Polynomial2DTransform
    generally used by TransformList

    2nd
    dataString = dataString representation of transform from mpicpg

    3rd
    identity = make this transform the identity

    4th
    params = 2xK np.array of polynomial coefficents up to order K

    5th
    src,dst = Nx2 np.array of source and dst points to use to estimate
    transformation
    order = integer degree of polynomial to fit when using src,dst


    TODO:
        fall back to Affine Model in special cases
    '''
    className = 'mpicbg.trakem2.transform.PolynomialTransform2D'

    def __init__(self, dataString=None, src=None, dst=None, order=2,
                 force_polynomial=True, params=None, identity=False,
                 json=None, **kwargs):
        if json is not None:
            self.from_dict(json)
        else:
            self.className = 'mpicbg.trakem2.transform.PolynomialTransform2D'
            if dataString is not None:
                self._process_dataString(dataString)
            elif identity:
                self.params = np.array([[0, 1, 0], [0, 0, 1]])
            elif params is not None:
                self.params = params
            elif src is not None and dst is not None:
                self.estimate(src, dst, order, return_params=False, **kwargs)

            if not force_polynomial and self.is_affine:
                raise NotImplementedError('Falling back to Affine model is '
                                          'not supported {}')
            self.transformId = None

    @property
    def is_affine(self):
        '''TODO allow default to Affine'''
        return False
        # return self.order

    @property
    def order(self):
        no_coeffs = len(self.params.ravel())
        return int((abs(np.sqrt(4 * no_coeffs + 1)) - 3) / 2)

    @property
    def dataString(self):
        return Polynomial2DTransform._dataStringfromParams(self.params)

    @staticmethod
    def fit(src, dst, order=2):
        xs = src[:, 0]
        ys = src[:, 1]
        xd = dst[:, 0]
        yd = dst[:, 1]
        rows = src.shape[0]
        no_coeff = (order + 1) * (order + 2)

        if len(src) != len(dst):
            raise EstimationError(
                'source has {} points, but dest has {}!'.format(
                    len(src), len(dst)))
        if no_coeff > len(src):
            raise EstimationError(
                'order {} is too large to fit {} points!'.format(
                    order, len(src)))

        A = np.zeros([rows * 2, no_coeff + 1])
        pidx = 0
        for j in range(order + 1):
            for i in range(j + 1):
                A[:rows, pidx] = xs ** (j - i) * ys ** i
                A[rows:, pidx + no_coeff // 2] = xs ** (j - i) * ys ** i
                pidx += 1

        A[:rows, -1] = xd
        A[rows:, -1] = yd

        # right singular vector corresponding to smallest singular value
        _, s, V = svd(A)
        Vsm = V[np.argmin(s), :]  # never trust computers
        return (-Vsm[:-1] / Vsm[-1]).reshape((2, no_coeff // 2))

    def estimate(self, src, dst, order=2,
                 test_coords=True, max_tries=100, return_params=True,
                 **kwargs):
        def fitgood(src, dst, params, atol=1e-3, rtol=0, **kwargs):
            result = Polynomial2DTransform(params=params).tform(src)
            t = np.allclose(
                result, dst,
                atol=atol, rtol=rtol)
            return t

        estimated = False
        tries = 0
        while (tries < max_tries and not estimated):
            tries += 1
            try:
                params = Polynomial2DTransform.fit(src, dst, order=order)
            except (LinAlgError, ValueError) as e:
                logger.debug('Encountered error {}'.format(e))
                continue
            estimated = (fitgood(src, dst, params, **kwargs) if
                         test_coords else True)

        if tries == max_tries and not estimated:
            raise EstimationError('Could not fit Polynomial '
                                  'in {} attempts!'.format(tries))
        logger.debug('fit parameters in {} attempts'.format(tries))
        self.params = params
        if return_params:
            return self.params

    @staticmethod
    def _dataStringfromParams(params=None):
        return ' '.join([str(i).replace('e-0', 'e-').replace('e+0', 'e+')
                         for i in params.flatten()]).replace('e', 'E')

    def _process_dataString(self, datastring):
        '''
        generate datastring and param attributes from datastring
        '''
        dsList = datastring.split(' ')
        self.params = Polynomial2DTransform._format_raveled_params(dsList)

    @staticmethod
    def _format_raveled_params(raveled_params):
        return np.array(
            [[float(d) for d in raveled_params[:len(raveled_params)/2]],
             [float(d) for d in raveled_params[len(raveled_params)/2:]]])

    def tform(self, points):
        dst = np.zeros(points.shape)
        x = points[:, 0]
        y = points[:, 1]

        o = int((-3 + np.sqrt(9 - 4 * (2 - len(self.params.ravel())))) / 2)
        pidx = 0
        for j in range(o + 1):
            for i in range(j + 1):
                dst[:, 0] += self.params[0, pidx] * x ** (j - i) * y ** i
                dst[:, 1] += self.params[1, pidx] * x ** (j - i) * y ** i
                pidx += 1
        return dst

    def coefficients(self, order=None):
        '''
        determine number of coefficient terms in transform for a given order
        input: order of polynomial -- defaults to self.order
        output: integer number of coefficient terms expected in transform
        '''
        if order is None:
            order = self.order
        return (order + 1) * (order + 2)

    def asorder(self, order):
        '''
        input: order > current order
        output: new Transform object of selected order with coefficients
            from self
        '''
        if self.order > order:
            raise ConversionError(
                'transformation {} is order {} -- conversion to '
                'order {} not supported'.format(
                    self.dataString, self.order, order))
        new_params = np.zeros([2, self.coefficients(order) // 2])
        new_params[:self.params.shape[0], :self.params.shape[1]] = self.params
        return Polynomial2DTransform(params=new_params)

    @staticmethod
    def fromAffine(aff):
        '''
        input: AffineModel
        output: Polynomial2DTransform defined by Affine model
        '''
        if not isinstance(aff, AffineModel):
            raise ConversionError('attempting to convert a nonaffine model!')
        return Polynomial2DTransform(order=1, params=np.array([
            [aff.M[0, 2], aff.M[0, 0], aff.M[0, 1]],
            [aff.M[1, 2], aff.M[1, 0], aff.M[1, 1]]]))


def estimate_dstpts(transformlist, src=None):
    '''
    estimate destination points for list of transforms
    input:
        transformlist -- list of transform classes with tform method
        src -- Nx2 numpy array of source points
    output: Nx2 numpt array of destination points
    '''
    dstpts = src
    for tform in transformlist:
        if isinstance(tform, list):
            dstpts = estimate_dstpts(tform, dstpts)
        else:
            dstpts = tform.tform(dstpts)
    return dstpts


def estimate_transformsum(transformlist, src=None, order=2):
    '''
    pseudo-composition of transforms in list of transforms using source point
        transformation and a single estimation.
        Will produce an Affine Model if all input transforms are Affine,
           otherwise will produce a Polynomial of specified order
    inputs:
        transformlist: recursive list of transform objects
        src: Nx2 numpy array of source points for estimation
        order: optional, order of Polynomial output if transformlist
            inputs are non-Affine
    '''
    def flatten(l):
        for i in l:
            if (isinstance(i, Iterable) and not
                    isinstance(i, basestring)):
                for sub in flatten(i):
                    yield sub
            else:
                yield i

    dstpts = estimate_dstpts(transformlist, src)
    tforms = flatten(transformlist)
    if all([tform.className == AffineModel.className
            for tform in tforms]):
                am = AffineModel()
                am.estimate(A=src, B=dstpts, return_params=False)
                return am
    return Polynomial2DTransform(src=src, dst=dstpts, order=order)

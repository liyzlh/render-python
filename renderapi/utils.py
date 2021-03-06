#!/usr/bin/env python
'''
utilities to make render/java/web/life interfacing easier
'''
import tempfile
import logging
import inspect
import copy
import json
from .errors import RenderError


class NullHandler(logging.Handler):
    '''handler to avoid logging errors for, e.g., missing logger setup'''
    def emit(self, record):
        pass


logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())


class RenderEncoder(json.JSONEncoder):
    '''
    json Encoder in the following hierarchy for serialization:
        obj.to_dict()
        dict(obj)
        JsonEncoder.default(obj)
        obj.__dict__
    '''
    def default(self, obj):
        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            return obj.to_dict()
        else:
            try:
                return dict(obj)
            except TypeError as e:
                logger.debug("{} object is not recognized dictionary".format(
                    type(obj)))
                try:
                    return super(RenderEncoder, self).default(obj)
                except TypeError as e:  # pragma: no cover
                    logger.info(e)
                    logger.warning(
                        "cannot json serialize {}.  "
                        "Defaulting to __dict__".format(type(obj)))
                    return obj.__dict__


def post_json(session, request_url, d, params=None):
    headers = {"content-type": "application/json"}
    if d is not None:
        payload = json.dumps(d)
    else:
        payload = None
        headers['Accept'] = "application/json"
    r = session.post(request_url, data=payload, params=params,
                     headers=headers)
    try:
        return r
    except Exception as e:
        logger.error(e)
        logger.error(r.text)
        raise RenderError(
            'cannot post {} to {} with params {}'.format(
                d, request_url, params))


def put_json(session, request_url, d, params=None):
    headers = {"content-type": "application/json"}
    if d is not None:
        payload = json.dumps(d)
    else:
        payload = None
        headers['Accept'] = "application/json"
    r = session.put(request_url, data=payload, params=params,
                    headers=headers)
    try:
        return r
    except Exception as e:
        logger.error(e)
        logger.error(r.text)
        raise RenderError(
            'cannot put {} to {} with params {}'.format(
                d, request_url, params))


def renderdumps(obj, *args, **kwargs):
    '''json.dumps using the RenderEncoder'''
    cls_ = kwargs.pop('cls', RenderEncoder)
    return json.dumps(obj, *args, cls=cls_, **kwargs)


def renderdump(obj, *args, **kwargs):
    '''json.dump using the RenderEncoder'''
    cls_ = kwargs.pop('cls', RenderEncoder)
    return json.dump(obj, *args, cls=cls_, **kwargs)


def renderdump_temp(obj, *args, **kwargs):
    '''json.dump into a temporary file
    renderdump_temp(obj), obj will be dumped through renderdump
    into a temporary file
    returns tempfilename, path to file it was dumped into'''
    with tempfile.NamedTemporaryFile(
            suffix=".json", mode='w', delete=False) as tf:
        tempfilename = tf.name
        renderdump(obj, tf, *args, **kwargs)
    return tempfilename


def jbool(val):
    '''return string representing java string values of py booleans'''
    if not isinstance(val, bool):
        logger.warning('Evaluating javastring of non-boolean {} {}'.format(
            type(val), val))
    return 'true' if val else 'false'


def stripLogger(logger_tostrip):  # pragma: no cover
    '''
    remove all handlers from a logger -- useful for redefining
    input:
        logger_tostrip: logging logger as from logging.getLogger
    '''
    if logger_tostrip.handlers:
        for handler in logger_tostrip.handlers:
            logger_tostrip.removeHandler(handler)


def defaultifNone(val, default=None):
    return val if val is not None else default


def fitargspec(f, oldargs, oldkwargs):
    ''' fit function argspec given input args tuple and kwargs dict'''
    try:
        args, varargs, keywords, defaults = inspect.getargspec(f)
        num_expected_args = len(args) - len(defaults)
        new_args = tuple(oldargs[:num_expected_args])
        new_kwargs = copy.copy(oldkwargs)
        for i, arg in enumerate(oldargs[num_expected_args:]):
            new_kwargs.update({args[i + num_expected_args]: arg})
        return new_args, new_kwargs
    except Exception as e:
        logger.error('Cannot fit argspec for {}'.format(f))
        logger.error(e)
        return oldargs, oldkwargs

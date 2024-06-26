###
### Copyright (C) 2023 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

import os
import slash
from enum import Enum

Scope     = Enum("Scope", dict(TEST = "test", SESSION = "session-global"), type = str)
Retention = Enum("Retention", ["NONE", "FAIL", "ALL"], start = 0, type = int)

class Artifacts():
  def __init__(self, retention):
    self._retention = Retention(retention)

  @property
  def retention(self):
    return self._retention

  def __result(self, scope):
    return {
      Scope.TEST    : slash.context.result,
      Scope.SESSION : slash.session.results.global_result
    }[scope]

  def __id(self, scope):
    return {
      Scope.TEST    : slash.context.test.id,
      Scope.SESSION : slash.session.id,
    }[scope]

  def purge(self, filename, scope = Scope.TEST):
    result = self.__result(scope)
    if Retention.ALL != self.retention:
      if Retention.FAIL == self.retention and not result.is_success():
        pass # Keep artifact on failure
      elif filename in result.data.get("artifacts", list()):
        if os.path.exists(filename):
          os.remove(filename)

  def reserve(self, ext, scope = Scope.TEST):
    result = self.__result(scope)
    artifacts = result.data.setdefault("artifacts", list())
    filename = f"{self.__id(scope)}_{len(artifacts)}.{ext}"
    absfile = os.path.join(result.get_log_dir(), filename)
    artifacts.append(absfile)
    slash.add_critical_cleanup(self.purge, scope = scope, args = (absfile, scope))
    return absfile

class MediaAssets:
  def __init__(self):
    # cache files that have already been decoded during the test session
    self._decoded = dict()

  def register(self, params):
    from .codecs import Codec

    # ignore RAW or unspecified codec assets
    if params.get("scodec", Codec.RAW) is Codec.RAW:
      return

    source  = params["source"]
    format  = params["format"]
    frames  = params.get("brframes", params["frames"])

    entry = self._decoded.setdefault(
      (source, format), dict(frames = frames, decoded = None))

    if frames > entry["frames"]:
      entry["frames"] = frames

  def raw(self, test, **kwargs):
    from .codecs import Codec
    if vars(test).get("scodec", Codec.RAW) is Codec.RAW:
      return test.source

    entry = self._decoded[(test.source, test.format)]
    if entry["decoded"] is None:
      decoder = test.DecoderClass(
        scope = Scope.SESSION,
        frames = entry["frames"],
        format = test.format,
        source = test.source,
        **kwargs,
      )
      decoder.decode()
      entry["decoded"] = decoder.decoded
    return entry["decoded"]

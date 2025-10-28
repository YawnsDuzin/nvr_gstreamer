"""
Mock gi module for testing without GStreamer
This file allows testing UI components without GStreamer dependencies
"""

import sys
from unittest.mock import MagicMock

# Create mock gi module
gi = MagicMock()
gi.require_version = MagicMock()

# Create mock Gst module
Gst = MagicMock()
Gst.init = MagicMock()
Gst.State = MagicMock()
Gst.State.NULL = 0
Gst.State.PLAYING = 4
Gst.StateChangeReturn = MagicMock()
Gst.StateChangeReturn.FAILURE = 0
Gst.StateChangeReturn.SUCCESS = 1
Gst.MessageType = MagicMock()
Gst.MessageType.EOS = 1
Gst.MessageType.ERROR = 2
Gst.MessageType.WARNING = 3
Gst.MessageType.STATE_CHANGED = 4
Gst.FlowReturn = MagicMock()
Gst.FlowReturn.OK = 0
Gst.parse_launch = MagicMock(return_value=MagicMock())
Gst.ElementFactory = MagicMock()
Gst.Registry = MagicMock()
Gst.Registry.get = MagicMock(return_value=MagicMock())

# Create mock GLib module
GLib = MagicMock()
GLib.MainLoop = MagicMock
GLib.Error = Exception

# Create mock GObject module
GObject = MagicMock()

# Create mock GstVideo module
GstVideo = MagicMock()

# Add to sys.modules
sys.modules['gi'] = gi
sys.modules['gi.repository'] = MagicMock()
sys.modules['gi.repository.Gst'] = Gst
sys.modules['gi.repository.GLib'] = GLib
sys.modules['gi.repository.GObject'] = GObject
sys.modules['gi.repository.GstVideo'] = GstVideo

print("Mock gi module loaded successfully")
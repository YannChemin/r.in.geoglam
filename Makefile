MODULE_TOPDIR = ../..

PGM = r.in.geoglam

include $(MODULE_TOPDIR)/include/Make/Script.make
include $(MODULE_TOPDIR)/include/Make/Html.make

default: script html

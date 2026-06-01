SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES = $(PWD)/vga_core.v

TOPLEVEL = vga_core

MODULE = bad-riscv

WAVES = 1

include $(shell cocotb-config --makefiles)/Makefile.sim

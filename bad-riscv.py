"""
Copyright (C) 2026 wirtnel

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
import pygame
import sys
import os
import ctypes
import numpy as np

# Desactivar el motor de audio de SDL si no lo usas, evita warnings
os.environ['SDL_AUDIODRIVER'] = 'dummy'

# load the compiled riscv emu, you can customize this as well, more info in the README section about the compiled lib
try:
    riscv = ctypes.CDLL("./extern/RV32I-emu/libcorerv32.so")
except OSError:
    print("Error: libcorerv32.so not found")
    sys.exit(1)

class BUS(ctypes.Structure):
    # 42 MiB RAM (this should be the same as in dram.h if manually compiling the lib, I doubt you will use more than this ammount)
    _fields_ = [("dram_memory", ctypes.c_uint8 * (42 * 1024 * 1024))]

class RISCV_CPU(ctypes.Structure):
    _fields_ = [
        ("regs", ctypes.c_uint32 * 32),
        ("pc", ctypes.c_uint32),
        ("bus", BUS),
        ("running", ctypes.c_bool)
    ]

# simulation
@cocotb.test()
async def test_vga_display(dut):
    # cpu init
    cpu = RISCV_CPU()
    riscv.cpu_init(ctypes.byref(cpu), 0x00000000) # starts at 0
    vram_start_addr = 0x000F0000 # vram starts here, as defined in the riscv-emu
    asset_base_addr = 0x00200000 # program gets load here

    # load binary to RAM
    try:
        with open("video.bin", "rb") as f:
            video_data = f.read()
            video_size = len(video_data)
            print(f"[COCOTB] Loading {video_size} bytes to RAM...")
            # Actually moving the memory to the program (a bit slow, but faster than I thought)
            dst_ptr = ctypes.addressof(cpu.bus.dram_memory) + asset_base_addr
            ctypes.memmove(dst_ptr, video_data, video_size)
    except FileNotFoundError:
        print("[COCOTB] video.bin not found.")

    # Loading "firmware" to the cpu, I tried to simplify this in assembly, unironically my riscv-tui turned out to be helpful for this
    program = [
        0x000f0537, # 0x00: lui  x10, 0x000f0       (VRAM)
        0x002005b7, # 0x04: lui  x11, 0x00200       (ASSET)
        # next_frame:
        0x000506b3, # 0x08: add  x13, x10, zero
        0x00058733, # 0x0C: add  x14, x11, zero
        0x12c00793, # 0x10: addi x15, zero, 300     (1200 bytes / 4 = 300 word)
        0x00000013, # 0x14: nop                     (align loop)
        # copy_loop:
        0x00072803, # 0x18: lw   x16, 0(x14)
        0x0106a023, # 0x1C: sw   x16, 0(x13)
        0x00470713, # 0x20: addi x14, x14, 4
        0x00468693, # 0x24: addi x13, x13, 4
        0xfff78793, # 0x28: addi x15, x15, -1
        0xfe0796e3, # 0x2C: bne  x15, zero, -20
        # end_frame:
        0x000705b3, # 0x30: add  x11, x14, zero
        0xfd5ff06f  # 0x34: jal  zero, -44
    ]

    for i, inst in enumerate(program):
        riscv.bus_write32(ctypes.byref(cpu.bus), i * 4, inst)

    # pygame init (If you can use something different from pygame, it would most likely be better, sadly this is the only library I know how to use)
    pygame.init()
    width, height = 640, 480 # fun fact, this was the original intended resolution to use for the video conversion, but it was extremely slow
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("RV32I EMULATOR + VGA COCOTB")

    # verilog signal config
    # 25MHz (40ns)
    cocotb.start_soon(Clock(dut.clk, 40, units="ns").start())

    # VGA reset
    dut.rst.value = 1
    await Timer(100, units="ns")
    dut.rst.value = 0

    # cpu-screen sync var
    cpu_wait_for_vsync = False

    # coroutine: cpu execution
    async def run_cpu():
        nonlocal cpu_wait_for_vsync
        while True:
            await RisingEdge(dut.clk)

            # OVERCLOCK: cpu does 4 cycles per VGA life-cycle
            # like a 100mhz cpu with a 25mhz video bus?
            for _ in range(4):
                if cpu.running and not cpu_wait_for_vsync:
                    riscv.execute_step(ctypes.byref(cpu))

                    # The 0x30 instruction marks the end of frame copying
                    if cpu.pc == 0x30: 
                        cpu_wait_for_vsync = True

                        riscv.execute_step(ctypes.byref(cpu)) 
                        riscv.execute_step(ctypes.byref(cpu))

    cocotb.start_soon(run_cpu())

    print("\n[COCOTB] Simulation started...\n")

    # main loop
    while True:
        # await Verilog vsync pulse
        await FallingEdge(dut.v_sync) 

        # vram extract
        vram_end_addr = vram_start_addr + (40 * 30)

        # This really improved performance, as I noticed the bottleneck was in the memory reading, so my idea is to read from a buffer faster with numpy
        full_memory = np.frombuffer(cpu.bus.dram_memory, dtype=np.uint8)

        # only extract the vram segment
        vram_array = full_memory[vram_start_addr:vram_end_addr].reshape((30, 40))

        # color stuff (RGB332)
        r = ((vram_array >> 5) & 0x07) * 36
        g = ((vram_array >> 2) & 0x07) * 36
        b = (vram_array & 0x03) * 85

        rgb_array = np.dstack((r, g, b)).astype(np.uint8)
        rgb_array = np.transpose(rgb_array, (1, 0, 2))

        # pygame rendering
        small_surface = pygame.surfarray.make_surface(rgb_array)
        pygame.transform.scale(small_surface, (width, height), screen)

        pygame.display.flip()

        # Frame ends, cpu awakes for next one
        cpu_wait_for_vsync = False

        # pygame window safe exit
        exit_simulation = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit_simulation = True

        if exit_simulation:
            break

        # wait for high signal to not activate multiple times
        await RisingEdge(dut.v_sync)

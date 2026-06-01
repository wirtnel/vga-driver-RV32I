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
from cocotb.triggers import RisingEdge, Timer
import pygame
import sys
import os
import ctypes

os.environ['SDL_AUDIODRIVER'] = 'dummy'

try:
    riscv = ctypes.CDLL("./libcorerv32.so")
except OSError:
    try:
        riscv = ctypes.CDLL("./extern/RV32I-emu/libcorerv32.so")
    except OSError:
        sys.exit(1)

class BUS(ctypes.Structure):
    _fields_ = [("dram_memory", ctypes.c_uint8 * (42 * 1024 * 1024))]  

class RISCV_CPU(ctypes.Structure):
    _fields_ = [
        ("regs", ctypes.c_uint32 * 32),
        ("pc", ctypes.c_uint32),
        ("bus", BUS),
        ("running", ctypes.c_bool)
    ]
riscv.print_state.argtypes = [ctypes.POINTER(RISCV_CPU), ctypes.c_uint32]
riscv.print_state.restype = None

@cocotb.test()
async def test_vga_display(dut):
    cpu = RISCV_CPU()
    riscv.cpu_init(ctypes.byref(cpu), 0x00000000)
    instr = riscv.bus_read32(ctypes.byref(cpu.bus), cpu.pc)
    vram_start_addr = 0x000F0000

    for y in range(120):
        for x in range(160):
            addr = vram_start_addr + (y * 160 + x)
            if y < 40:
                color = 0xE0
            elif y < 80:
                color = 0x1C
            else:
                color = 0x03
            cpu.bus.dram_memory[addr] = color

    pygame.init()
    width, height = 640, 480
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("RV32I VGA Pattern Test")
    framebuffer = pygame.Surface((width, height))

    dut.rst.value = 1
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())

    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst.value = 0

    while True:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if cpu.running:
            prev_pc = cpu.pc
            riscv.execute_step(ctypes.byref(cpu))
            print(f"[TESTBENCH] CPU stepped from 0x{prev_pc:08x} to 0x{cpu.pc:08x}")
            riscv.print_state(ctypes.byref(cpu), instr)
            vram_start = 0x000F0000
            # Imprime un segmento de la VRAM si el PC cambió
            print(f"[VRAM MONITOR] Primeros bytes de VRAM: {list(cpu.bus.dram_memory[vram_start:vram_start+8])}")
        if int(dut.h_count.value) == 0 and int(dut.v_count.value) == 0:
            for y_log in range(120):
                for x_log in range(160):
                    addr = vram_start_addr + (y_log * 160 + x_log)
                    raw = cpu.bus.dram_memory[addr]

                    r = (raw >> 5) & 0x07
                    g = (raw >> 2) & 0x07
                    b = raw & 0x03
                    rgb = (r * 36, g * 36, b * 85)

                    for dy in range(4):
                        for dx in range(4):
                            framebuffer.set_at((x_log * 4 + dx, y_log * 4 + dy), rgb)

            screen.blit(framebuffer, (0, 0))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

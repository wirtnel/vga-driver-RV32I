/*
* =========================================================================
* Module Name:    vga_core
* Project:        RV32I VGA Driver & Co-Simulation Environment
* Author:         wakuroshi
* Date:           2026
*
* Description:    Generates structural horizontal and vertical timing
* synchronization signals (h_sync, v_sync) for a standard
* 640x480 @ 60Hz display matrix. Drives pixel coordinate 
* validation counters for upstream video memory pipes.
*
* Dependencies:   None (Internal clock dividers scale the system clock)
* =========================================================================
* COPYRIGHT & LICENSE NOTICE
* =========================================================================
* Copyright (C) 2026 wakuroshi
*
* This program is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* This program is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/


`timescale 1ns / 1ps

module vga_core (
    input  wire       clk,      // System clock
    input  wire       rst,      // Asynchronous reset (active high)
    output reg  [9:0] h_count,  // Horizontal pixel counter
    output reg  [9:0] v_count,  // Vertical line counter
    output reg        h_sync,   // Horizontal sync signal
    output reg        v_sync,   // Vertical sync signal
    output reg        video_on, // Active video region flag
    output wire [7:0] vga_rgb   // RGB output data
);

    // VGA Timing Parameters
    // Defined in pixels/lines based on the resolution requirements
    // H Sync timings
    localparam HD = 40;              // Horizontal Active Display area
    localparam HF = 1;               // Horizontal Front Porch
    localparam HB = 3;               // Horizontal Back Porch
    localparam HR = 6;               // Horizontal Retrace (Sync pulse)
    localparam HMAX = HD+HF+HB+HR;   // Total horizontal period: 50

    // V Sync timings
    localparam VD = 30;              // Vertical Active Display area
    localparam VF = 1;               // Vertical Front Porch
    localparam VB = 2;               // Vertical Back Porch
    localparam VR = 1;               // Vertical Retrace (Sync pulse)
    localparam VMAX = VD+VF+VB+VR;   // Total vertical period: 34

    // coord gen
    // increments the horizontal counter; when it reaches the end, resets it and increments the vertical line counter
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            h_count <= 10'd0;
            v_count <= 10'd0;
        end else begin
            if (h_count == HMAX - 1) begin
                h_count <= 10'd0;
                if (v_count == VMAX - 1) begin
                    v_count <= 10'd0;
                end else begin
                    v_count <= v_count + 10'd1;
                end
            end else begin
                h_count <= h_count + 10'd1;
            end
        end
    end

    // Signal gen
    // VGA sync pulses are typically active-low
    // h_sync/v_sync are asserted low during the Retrace (HR/VR) period
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            h_sync <= 1'b1;
            v_sync <= 1'b1;
        end else begin
            // Pulse is low when the counter is within the Retrace range
            h_sync <= ~((h_count >= (HD + HF)) && (h_count < (HD + HF + HR)));
            v_sync <= ~((v_count >= (VD + VF)) && (v_count < (VD + VF + VR)));
        end
    end

    // active video region
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            video_on <= 1'b0;
        end else begin
            video_on <= (h_count < HD) && (v_count < VD);
        end
    end

    // rgb data output
    assign vga_rgb = (video_on) ? 8'hff : 8'h00;


endmodule

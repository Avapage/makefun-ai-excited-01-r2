#!/usr/bin/env python3
"""Starwhale Ascendant - a deterministic procedural renderer.

Draws a colossal whale made of living starlight breaching upward out of a
sea of clouds at night: a spiral galaxy turns inside its body, a huge full
moon is haloed directly behind it, arcs of luminous spray fly with it, and
one tiny warm-lit lighthouse on a dark rock far below gives the scale.

Pure Python 3 standard library. Fixed seeds only - no wall clock, no
network, no varying randomness: two runs produce byte-identical PNG bytes.

Run:  python3 main.py   ->   writes /output/entry.png (1024 x 1024)
"""

import math
import os
import struct
import zlib
from array import array

# ------------------------------------------------------------------ sizes
S = 1024                    # final image edge
SS = 2                      # supersampling factor
R = S * SS                  # render edge (2048)
OUT = "/output/entry.png"

MOON_X = 0.560 * R
MOON_Y = 0.330 * R
MOON_R = 0.180 * R
BREACH_X = 0.700 * R


# ------------------------------------------------------------------ utils
def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    return t * t * (3.0 - 2.0 * t)


class Lcg:
    """Deterministic linear congruential generator (fixed seed)."""

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFF

    def next(self):
        self.state = (self.state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.state / 4294967296.0

    def range(self, a, b):
        return a + (b - a) * self.next()


def hash2(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 974634211) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) & 0xFFFFFFFF
    h = (h * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return h / 4294967296.0


def make_noise(n, cell, seed):
    """Smooth value-noise byte field, n x n, lattice spacing `cell` px."""
    gw = int(n / cell) + 3
    lat = [hash2(i, j, seed) for j in range(gw) for i in range(gw)]
    out = bytearray(n * n)
    inv = 1.0 / cell
    for y in range(n):
        gy = y * inv
        iy = int(gy)
        fy = smooth(gy - iy)
        lrow = iy * gw
        row = y * n
        for x in range(n):
            gx = x * inv
            ix = int(gx)
            fx = smooth(gx - ix)
            i0 = lrow + ix
            v00 = lat[i0]
            v10 = lat[i0 + 1]
            v01 = lat[i0 + gw]
            v11 = lat[i0 + gw + 1]
            top = v00 + (v10 - v00) * fx
            bot = v01 + (v11 - v01) * fx
            out[row + x] = int((top + (bot - top) * fy) * 255.0)
    return out


def shade_dot(img, cx, cy, rad, cr, cg, cb, peak):
    """Blend a soft dot toward a fixed colour (for dark details)."""
    x0 = max(0, int(cx - rad - 1))
    x1 = min(R - 1, int(cx + rad + 1))
    y0 = max(0, int(cy - rad - 1))
    y1 = min(R - 1, int(cy + rad + 1))
    inv = 1.0 / (rad * rad)
    for y in range(y0, y1 + 1):
        dy = y - cy
        base = y * R * 3
        for x in range(x0, x1 + 1):
            dx = x - cx
            q = (dx * dx + dy * dy) * inv
            if q >= 1.0:
                continue
            w = (1.0 - q) * (1.0 - q) * peak
            i3 = base + x * 3
            img[i3] = int(img[i3] * (1.0 - w) + cr * w)
            img[i3 + 1] = int(img[i3 + 1] * (1.0 - w) + cg * w)
            img[i3 + 2] = int(img[i3 + 2] * (1.0 - w) + cb * w)


def splat(img, cx, cy, rad, cr, cg, cb, peak):
    """Additive dot with quadratic falloff."""
    x0 = max(0, int(cx - rad - 1))
    x1 = min(R - 1, int(cx + rad + 1))
    y0 = max(0, int(cy - rad - 1))
    y1 = min(R - 1, int(cy + rad + 1))
    inv = 1.0 / (rad * rad)
    for y in range(y0, y1 + 1):
        dy = y - cy
        base = y * R * 3
        for x in range(x0, x1 + 1):
            dx = x - cx
            q = (dx * dx + dy * dy) * inv
            if q >= 1.0:
                continue
            w = (1.0 - q) * (1.0 - q) * peak
            i3 = base + x * 3
            v = img[i3] + cr * w
            img[i3] = 255 if v > 255 else int(v)
            v = img[i3 + 1] + cg * w
            img[i3 + 1] = 255 if v > 255 else int(v)
            v = img[i3 + 2] + cb * w
            img[i3 + 2] = 255 if v > 255 else int(v)


# ------------------------------------------------------------------ sky
def paint_sky(img, neb_a, neb_b):
    stops = ((0.0, (3, 5, 16)), (0.42, (8, 12, 36)),
             (0.72, (13, 19, 50)), (1.0, (5, 7, 20)))
    for y in range(R):
        ty = y / R
        br = bg = bb = 0.0
        for k in range(3):
            if ty <= stops[k + 1][0] or k == 2:
                t0, c0 = stops[k]
                t1, c1 = stops[k + 1]
                f = (ty - t0) / (t1 - t0)
                br = c0[0] + (c1[0] - c0[0]) * f
                bg = c0[1] + (c1[1] - c0[1]) * f
                bb = c0[2] + (c1[2] - c0[2]) * f
                break
        nrow = (y >> 1) * S
        base = y * R * 3
        for x in range(R):
            ni = nrow + (x >> 1)
            va = neb_a[ni] * 0.0039215686
            vb = neb_b[ni] * 0.0039215686
            va2 = va * va
            vb2 = vb * vb
            i3 = base + x * 3
            img[i3] = int(br + 46.0 * va2 + 5.0 * vb2)
            img[i3 + 1] = int(bg + 25.0 * va2 + 26.0 * vb2)
            img[i3 + 2] = int(bb + 90.0 * va2 + 38.0 * vb2)


def paint_stars(img, rng):
    tints = ((225, 235, 255), (255, 232, 196), (186, 224, 255),
             (240, 244, 255))
    for _ in range(1250):
        x = rng.next() * R
        y = (rng.next() ** 1.25) * R * 0.99
        b = 0.25 + 0.75 * (rng.next() ** 2)
        tint = tints[int(rng.next() * 4) % 4]
        kind = rng.next()
        if kind < 0.68:
            rad = 1.6
        elif kind < 0.93:
            rad = 2.6
        else:
            rad = 3.8
        splat(img, x, y, rad, tint[0], tint[1], tint[2], b * 0.85)


# ------------------------------------------------------------------ moon
def paint_moon(img, neb_b):
    # halo
    hr = MOON_R * 1.78
    hr2 = hr * hr
    x0 = max(0, int(MOON_X - hr - 1))
    x1 = min(R - 1, int(MOON_X + hr + 1))
    y0 = max(0, int(MOON_Y - hr - 1))
    y1 = min(R - 1, int(MOON_Y + hr + 1))
    for y in range(y0, y1 + 1):
        dy = y - MOON_Y
        base = y * R * 3
        for x in range(x0, x1 + 1):
            dx = x - MOON_X
            d2 = dx * dx + dy * dy
            if d2 >= hr2:
                continue
            d = math.sqrt(d2)
            if d < MOON_R * 0.82:
                continue
            t = clamp((d - MOON_R * 0.82) / (hr - MOON_R * 0.82), 0.0, 1.0)
            g = (1.0 - t) ** 1.8 * 0.55
            i3 = base + x * 3
            v = img[i3] + 138.0 * g
            img[i3] = 255 if v > 255 else int(v)
            v = img[i3 + 1] + 150.0 * g
            img[i3 + 1] = 255 if v > 255 else int(v)
            v = img[i3 + 2] + 188.0 * g
            img[i3 + 2] = 255 if v > 255 else int(v)
    # disc
    x0 = max(0, int(MOON_X - MOON_R - 2))
    x1 = min(R - 1, int(MOON_X + MOON_R + 2))
    y0 = max(0, int(MOON_Y - MOON_R - 2))
    y1 = min(R - 1, int(MOON_Y + MOON_R + 2))
    for y in range(y0, y1 + 1):
        dy = y - MOON_Y
        base = y * R * 3
        nrow = (y >> 1) * S
        for x in range(x0, x1 + 1):
            dx = x - MOON_X
            d = math.sqrt(dx * dx + dy * dy)
            cov = clamp(0.5 + (MOON_R - d) / 1.6, 0.0, 1.0)
            if cov <= 0.0:
                continue
            dn = d / MOON_R
            shade = 0.84 + 0.16 * (1.0 - dn * dn)
            mv = neb_b[nrow + (x >> 1)] * 0.0039215686
            m = clamp((mv - 0.52) * 2.4, 0.0, 1.0) * 0.17
            cr = (206.0 * (1.0 - m) + 148.0 * m) * shade + 13.0 * (1.0 - dn)
            cg = (214.0 * (1.0 - m) + 158.0 * m) * shade + 7.0 * (1.0 - dn)
            cb = (230.0 * (1.0 - m) + 188.0 * m) * shade
            i3 = base + x * 3
            ic = 1.0 - cov
            img[i3] = int(img[i3] * ic + cr * cov)
            img[i3 + 1] = int(img[i3 + 1] * ic + cg * cov)
            img[i3 + 2] = int(img[i3 + 2] * ic + cb * cov)


# ------------------------------------------------------------------ whale
SP = ((0.238, 0.212), (0.455, 0.118), (0.628, 0.352), (0.700, 0.585))
RKEYS = ((0.0, 0.25), (0.10, 0.56), (0.24, 0.90), (0.38, 1.00),
         (0.52, 0.97), (0.66, 0.80), (0.80, 0.52), (0.90, 0.30), (1.0, 0.16))
RB = 0.090 * R
NS = 110


def radius_at(t):
    for k in range(len(RKEYS) - 1):
        t0, s0 = RKEYS[k]
        t1, s1 = RKEYS[k + 1]
        if t <= t1 or k == len(RKEYS) - 2:
            u = clamp((t - t0) / (t1 - t0), 0.0, 1.0)
            return RB * (s0 + (s1 - s0) * smooth(u))
    return RB * RKEYS[-1][1]


def build_spine():
    pts = []
    for i in range(NS):
        t = i / (NS - 1)
        mt = 1.0 - t
        a = mt * mt * mt
        b = 3.0 * mt * mt * t
        c = 3.0 * mt * t * t
        d = t * t * t
        x = (a * SP[0][0] + b * SP[1][0] + c * SP[2][0] + d * SP[3][0]) * R
        y = (a * SP[0][1] + b * SP[1][1] + c * SP[2][1] + d * SP[3][1]) * R
        ex = (3.0 * mt * mt * (SP[1][0] - SP[0][0])
              + 6.0 * mt * t * (SP[2][0] - SP[1][0])
              + 3.0 * t * t * (SP[3][0] - SP[2][0]))
        ey = (3.0 * mt * mt * (SP[1][1] - SP[0][1])
              + 6.0 * mt * t * (SP[2][1] - SP[1][1])
              + 3.0 * t * t * (SP[3][1] - SP[2][1]))
        el = math.hypot(ex, ey) or 1.0
        pts.append((x, y, ex / el, ey / el, radius_at(t), t))
    return pts


def add_part(sdf, wu, wv, cx, cy, ax, ay, a, b, tval, vbase, vscale):
    """Union one tapered ellipse (fluke / fin) into the whale field."""
    rad = a + b
    x0 = max(0, int(cx - rad - 2))
    x1 = min(R - 1, int(cx + rad + 2))
    y0 = max(0, int(cy - rad - 2))
    y1 = min(R - 1, int(cy + rad + 2))
    ia = 1.0 / a
    ib = 1.0 / b
    for y in range(y0, y1 + 1):
        ry = y - cy
        row = y * R
        for x in range(x0, x1 + 1):
            rx = x - cx
            lx = rx * ax + ry * ay
            ly = -rx * ay + ry * ax
            q = (lx * ia) * (lx * ia) + (ly * ib) * (ly * ib)
            if q > 2.8:
                continue
            d = (math.sqrt(q) - 1.0) * b
            idx = row + x
            if d < sdf[idx]:
                sdf[idx] = d
                wu[idx] = tval
                wv[idx] = vbase + ly * vscale / R


def smooth_params(sdf, wu, wv):
    """One 3x3 smoothing pass over the whale's parameter field.

    The raw field comes from the nearest spine sample, which leaves faint
    creases where the nearest sample changes; the galaxy shading reads
    those creases as contour bands, so smooth them away (the silhouette
    itself stays in the untouched sdf array)."""
    su = array("f", wu)
    sv = array("f", wv)
    x0 = int(0.04 * R)
    x1 = int(0.97 * R)
    y0 = int(0.01 * R)
    y1 = int(0.82 * R)
    for y in range(y0, y1):
        row = y * R
        for x in range(x0, x1):
            idx = row + x
            if sdf[idx] > 40.0:
                continue
            au = 0.0
            av = 0.0
            n = 0
            for dj in (-R, 0, R):
                for di in (-1, 0, 1):
                    j = idx + dj + di
                    if sdf[j] < 40.0:
                        au += wu[j]
                        av += wv[j]
                        n += 1
            if n:
                su[idx] = au / n
                sv[idx] = av / n
    return su, sv


def build_whale_field(spine):
    sdf = array("f", [9999.0]) * (R * R)
    wu = array("f", [0.0]) * (R * R)
    wv = array("f", [0.0]) * (R * R)
    cell = 96
    gw = (R + cell - 1) // cell
    cells = [[] for _ in range(gw * gw)]
    for i, (x, y, tx, ty, rad, t) in enumerate(spine):
        m = rad + 30.0
        cx0 = max(0, int((x - m) // cell))
        cx1 = min(gw - 1, int((x + m) // cell))
        cy0 = max(0, int((y - m) // cell))
        cy1 = min(gw - 1, int((y + m) // cell))
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                cells[cy * gw + cx].append(i)
    for cy in range(gw):
        y0 = cy * cell
        y1 = min(R, y0 + cell)
        for cx in range(gw):
            lst = cells[cy * gw + cx]
            if not lst:
                continue
            x0 = cx * cell
            x1 = min(R, x0 + cell)
            for y in range(y0, y1):
                row = y * R
                for x in range(x0, x1):
                    best = 1e9
                    bi = -1
                    bd = 0.0
                    bdx = 0.0
                    bdy = 0.0
                    for i in lst:
                        sx, sy, stx, sty, srad, st = spine[i]
                        dx = x - sx
                        dy = y - sy
                        d = math.sqrt(dx * dx + dy * dy)
                        v = d - srad
                        if v < best:
                            best = v
                            bi = i
                            bd = d
                            bdx = dx
                            bdy = dy
                    idx = row + x
                    sdf[idx] = best
                    sx, sy, stx, sty, srad, st = spine[bi]
                    wu[idx] = st
                    cross = stx * bdy - sty * bdx
                    wv[idx] = (bd if cross >= 0.0 else -bd) / R
    # tail flukes
    x, y, tx, ty, rad, t = spine[-1]
    nx, ny = -ty, tx
    for side in (1.0, -1.0):
        cxp = x + tx * R * 0.012 + nx * side * 0.058 * R
        cyp = y + ty * R * 0.012 + ny * side * 0.058 * R
        ang = -side * 0.32
        ca = math.cos(ang)
        sa = math.sin(ang)
        ax = nx * ca - ny * sa
        ay = nx * sa + ny * ca
        add_part(sdf, wu, wv, cxp, cyp, ax, ay, 0.098 * R, 0.030 * R,
                 0.985, side * 0.03, 0.9)
    # pectoral fin on the belly side
    sp = spine[int(0.30 * (NS - 1))]
    x, y, tx, ty, rad, t = sp
    nx, ny = -ty, tx
    if (0.34 * R - x) * nx + (0.60 * R - y) * ny < 0.0:
        nx, ny = -nx, -ny
    cxp = x + nx * rad * 0.82
    cyp = y + ny * rad * 0.82
    ax = nx * 0.85 - tx * 0.5
    ay = ny * 0.85 - ty * 0.5
    al = math.hypot(ax, ay) or 1.0
    add_part(sdf, wu, wv, cxp, cyp, ax / al, ay / al, 0.072 * R, 0.021 * R,
             0.30, -0.10, 0.5)
    wu, wv = smooth_params(sdf, wu, wv)
    return sdf, wu, wv


def paint_whale(img, sdf, wu, wv, spine, rng, neb_b):
    x0 = int(0.05 * R)
    x1 = int(0.96 * R)
    y0 = int(0.02 * R)
    y1 = int(0.80 * R)
    for y in range(y0, y1):
        row = y * R
        base = row * 3
        for x in range(x0, x1):
            idx = row + x
            s = sdf[idx]
            if s > 34.0:
                continue
            i3 = base + x * 3
            if s > 0.5:
                # outer glow hugging the body
                g = math.exp(-s / 10.5)
                v = img[i3] + 44.0 * g
                img[i3] = 255 if v > 255 else int(v)
                v = img[i3 + 1] + 58.0 * g
                img[i3 + 1] = 255 if v > 255 else int(v)
                v = img[i3 + 2] + 132.0 * g
                img[i3 + 2] = 255 if v > 255 else int(v)
                continue
            # ---- interior: the galaxy inside the body
            tu = wu[idx]
            gx = (tu - 0.44) * 1.35
            gy = wv[idx] / 0.20
            r2 = gx * gx + gy * gy
            rr = math.sqrt(r2)
            th = math.atan2(gy, gx)
            core = math.exp(-r2 * 11.0)
            armc = 0.5 + 0.5 * math.cos(2.0 * th + 8.5 * rr)
            arm = (armc ** 3) * math.exp(-rr * 1.85)
            dust = ((1.0 - armc) ** 3) * math.exp(-rr * 1.85)
            ring = math.exp(-((rr - 0.62) * 2.4) ** 2)
            neb = (0.25 + 0.75 * arm) * math.exp(-rr * 1.1) * 0.9
            fg = math.exp(s / 15.0) * 0.5
            dv = (neb_b[((y >> 1) * S) + (x >> 1)] - 128) * 0.055
            cr = (13.0 + 60.0 * neb + 205.0 * arm + 27.0 * ring
                  + 120.0 * core + 95.0 * (core ** 2.4) + 34.0 * fg + dv)
            cg = (17.0 + 30.0 * neb + 84.0 * arm + 52.0 * ring
                  + 95.0 * core + 88.0 * (core ** 2.4) + 72.0 * fg + dv)
            cb = (45.0 + 104.0 * neb + 178.0 * arm + 108.0 * ring
                  + 58.0 * core + 80.0 * (core ** 2.4) + 138.0 * fg + dv)
            fd = 1.0 - 0.38 * dust
            cr *= fd
            cg *= fd
            cb *= fd
            if tu > 0.90:
                # the tail stock and flukes fall off into dim starlight
                tf = 1.0 - 0.62 * clamp((tu - 0.90) / 0.10, 0.0, 1.0)
                cr *= tf
                cg *= tf
                cb *= tf
            # ---- rim light, strongest on the moon side
            if s > -5.0:
                gx2 = sdf[idx + 1] - sdf[idx - 1]
                gy2 = sdf[idx + R] - sdf[idx - R]
                nl = math.sqrt(gx2 * gx2 + gy2 * gy2) or 1.0
                lx = MOON_X - x
                ly = MOON_Y - y
                ll = math.sqrt(lx * lx + ly * ly) or 1.0
                dot = (gx2 / nl) * (lx / ll) + (gy2 / nl) * (ly / ll)
                rb = clamp(1.0 - abs(s + 2.2) / 2.6, 0.0, 1.0)
                rim = rb * (0.45 + 0.55 * max(0.0, dot))
                cr += 168.0 * rim
                cg += 216.0 * rim
                cb += 255.0 * rim
                warm = rb * max(0.0, dot) ** 3 * 0.5
                cr += 255.0 * warm
                cg += 214.0 * warm
                cb += 150.0 * warm
            cov = clamp(0.5 - s / 1.4, 0.0, 1.0)
            ic = 1.0 - cov
            img[i3] = int(img[i3] * ic + min(cr, 255.0) * cov)
            img[i3 + 1] = int(img[i3 + 1] * ic + min(cg, 255.0) * cov)
            img[i3 + 2] = int(img[i3 + 2] * ic + min(cb, 255.0) * cov)
    # galaxy core glow, centred on the spine at t = 0.44
    cx, cy = spine[int(0.44 * (NS - 1))][0], spine[int(0.44 * (NS - 1))][1]
    splat(img, cx, cy, 34.0, 255, 205, 120, 0.30)
    # stars embedded in the body
    tints = ((205, 228, 255), (255, 240, 210), (190, 240, 255))
    for _ in range(460):
        x = rng.range(0.08 * R, 0.93 * R)
        y = rng.range(0.05 * R, 0.76 * R)
        if sdf[int(y) * R + int(x)] < -5.0:
            tint = tints[int(rng.next() * 3) % 3]
            rad = 2.4 if rng.next() < 0.18 else 1.5
            splat(img, x, y, rad, tint[0], tint[1], tint[2],
                  rng.range(0.5, 1.0))
    # one dark eye with a gold glint, near the nose on the belly side
    x, y, tx, ty, rad, t = spine[5]
    nx, ny = -ty, tx
    if (0.34 * R - x) * nx + (0.60 * R - y) * ny < 0.0:
        nx, ny = -nx, -ny
    ex = x + nx * rad * 0.38
    ey = y + ny * rad * 0.38
    for yy in range(int(ey - 8), int(ey + 9)):
        for xx in range(int(ex - 8), int(ex + 9)):
            d = math.hypot(xx - ex, yy - ey)
            if d < 7.5:
                w = clamp((7.5 - d) / 2.5, 0.0, 1.0) * 0.85
                i3 = (yy * R + xx) * 3
                img[i3] = int(img[i3] * (1.0 - w) + 5.0 * w)
                img[i3 + 1] = int(img[i3 + 1] * (1.0 - w) + 7.0 * w)
                img[i3 + 2] = int(img[i3 + 2] * (1.0 - w) + 18.0 * w)
    splat(img, ex + tx * 3.0, ey + ty * 3.0, 2.0, 255, 220, 150, 0.8)
    # a soft mouth curve sweeping under the head
    for k in range(40):
        tt = 0.03 + 0.17 * (k / 39.0)
        x, y, tx, ty, rad, _t = spine[int(tt * (NS - 1))]
        nx, ny = -ty, tx
        if (0.34 * R - x) * nx + (0.60 * R - y) * ny < 0.0:
            nx, ny = -nx, -ny
        shade_dot(img, x + nx * rad * 0.52 - tx * rad * 0.10,
                  y + ny * rad * 0.52 - ty * rad * 0.10,
                  7.0, 8, 10, 26, 0.20)


def paint_belly_droplets(img, spine, rng):
    """Water streaming off the underside of the breaching body."""
    for _ in range(30):
        t = 0.52 + 0.45 * rng.next()
        x, y, tx, ty, rad, _t = spine[int(t * (NS - 1))]
        nx, ny = -ty, tx
        if ny < 0.0:
            nx, ny = -nx, -ny
        for j in range(3):
            off = rad + 4.0 + j * 9.0 + rng.next() * 5.0
            px = x + nx * off - tx * j * j * 2.2 + (rng.next() - 0.5) * 6.0
            py = y + ny * off + j * j * 3.0
            splat(img, px, py, 2.0, 150, 198, 240, 0.5 + 0.35 * rng.next())


# ------------------------------------------------------------------ clouds
def cloud_top():
    by = []
    for x in range(R):
        xn = x / R
        by.append(R * (0.662 + 0.026 * math.sin(xn * 5.3 + 1.2)
                       + 0.016 * math.sin(xn * 11.9 + 4.0)
                       + 0.010 * math.sin(xn * 23.7 + 2.1)))
    return by


def paint_clouds(img, neb_b, by, rng):
    byb = by[int(BREACH_X)]
    y_start = int(0.55 * R)
    for y in range(y_start, R):
        row = y * R
        base = row * 3
        nrow = (y >> 1) * S
        for x in range(R):
            top = by[x]
            if y < top:
                continue
            depth = (y - top) / (R - top)
            if depth < 0.35:
                f = depth / 0.35
                cr = 30.0 + (15.0 - 30.0) * f
                cg = 41.0 + (21.0 - 41.0) * f
                cb = 80.0 + (48.0 - 80.0) * f
            else:
                f = (depth - 0.35) / 0.65
                cr = 15.0 + (4.0 - 15.0) * f
                cg = 21.0 + (6.0 - 21.0) * f
                cb = 48.0 + (15.0 - 48.0) * f
            tex = neb_b[nrow + (x >> 1)] * 0.0039215686
            mult = 0.84 + 0.32 * tex
            tl = math.exp(-(y - top) / 24.0)
            dx = x - BREACH_X
            dy = y - byb
            bg = math.exp(-(dx * dx + dy * dy) / (2.0 * 135.0 * 135.0))
            i3 = base + x * 3
            img[i3] = min(255, int(cr * mult + 92.0 * tl * 0.55
                                   + 84.0 * bg * 0.55))
            img[i3 + 1] = min(255, int(cg * mult + 112.0 * tl * 0.55
                                       + 124.0 * bg * 0.55))
            img[i3 + 2] = min(255, int(cb * mult + 164.0 * tl * 0.55
                                       + 186.0 * bg * 0.55))
    # soft puffs rolling over the cloud tops
    for _ in range(88):
        cx = rng.range(-40.0, R + 40.0)
        bx = int(clamp(cx, 0, R - 1))
        cy = by[bx] + rng.range(-26.0, 110.0)
        rx = rng.range(46.0, 165.0)
        ry = rx * rng.range(0.30, 0.45)
        shade = rng.next()
        cr = lerp(16.0, 46.0, shade)
        cg = lerp(23.0, 60.0, shade)
        cb = lerp(52.0, 106.0, shade)
        alpha = rng.range(0.30, 0.55)
        x0 = max(0, int(cx - rx - 1))
        x1 = min(R - 1, int(cx + rx + 1))
        y0 = max(0, int(cy - ry - 1))
        y1 = min(R - 1, int(cy + ry + 1))
        for yy in range(y0, y1 + 1):
            dyy = (yy - cy) / ry
            brow = yy * R * 3
            for xx in range(x0, x1 + 1):
                dxx = (xx - cx) / rx
                q = dxx * dxx + dyy * dyy
                if q >= 1.0:
                    continue
                w = (1.0 - q) * (1.0 - q) * alpha
                i3 = brow + xx * 3
                img[i3] = int(img[i3] * (1.0 - w) + cr * w)
                img[i3 + 1] = int(img[i3 + 1] * (1.0 - w) + cg * w)
                img[i3 + 2] = int(img[i3 + 2] * (1.0 - w) + cb * w)
    # bright crests catching the moonlight along the top edge
    for _ in range(12):
        cx = rng.range(0.0, R)
        bx = int(clamp(cx, 0, R - 1))
        cy = by[bx] - rng.range(4.0, 20.0)
        rx = rng.range(60.0, 130.0)
        ry = rx * 0.32
        x0 = max(0, int(cx - rx - 1))
        x1 = min(R - 1, int(cx + rx + 1))
        y0 = max(0, int(cy - ry - 1))
        y1 = min(R - 1, int(cy + ry + 1))
        for yy in range(y0, y1 + 1):
            dyy = (yy - cy) / ry
            brow = yy * R * 3
            for xx in range(x0, x1 + 1):
                dxx = (xx - cx) / rx
                q = dxx * dxx + dyy * dyy
                if q >= 1.0:
                    continue
                w = (1.0 - q) * (1.0 - q) * 0.35
                i3 = brow + xx * 3
                img[i3] = int(img[i3] * (1.0 - w) + 70.0 * w)
                img[i3 + 1] = int(img[i3 + 1] * (1.0 - w) + 88.0 * w)
                img[i3 + 2] = int(img[i3 + 2] * (1.0 - w) + 138.0 * w)


def paint_breach(img, by, rng):
    """The splash crown where the tail leaves the cloud sea."""
    byb = by[int(BREACH_X)]
    splat(img, BREACH_X, byb - 6.0, 130.0, 80, 120, 180, 0.38)
    for _ in range(60):
        vx = rng.range(-1.0, 1.0)
        vy = rng.range(0.4, 1.3)
        s = rng.next() ** 0.8
        px = BREACH_X + vx * s * 190.0 + (rng.next() - 0.5) * 8.0
        py = byb - vy * s * 170.0 + s * s * 150.0
        splat(img, px, py, rng.range(1.4, 3.2), 196, 232, 255,
              rng.range(0.5, 1.0))


# ------------------------------------------------------------------ lighthouse
def paint_lighthouse(img):
    lx = 0.150 * R
    # dark rock: three overlapping ellipses
    for (cx, cy, rx, ry) in ((lx, 0.908 * R, 128.0, 36.0),
                             (lx - 52.0, 0.920 * R, 84.0, 26.0),
                             (lx + 58.0, 0.922 * R, 74.0, 22.0)):
        x0 = max(0, int(cx - rx - 1))
        x1 = min(R - 1, int(cx + rx + 1))
        y0 = max(0, int(cy - ry - 1))
        y1 = min(R - 1, int(cy + ry + 1))
        for yy in range(y0, y1 + 1):
            dyy = (yy - cy) / ry
            brow = yy * R * 3
            for xx in range(x0, x1 + 1):
                dxx = (xx - cx) / rx
                q = dxx * dxx + dyy * dyy
                if q >= 1.0:
                    continue
                w = clamp((1.0 - q) * 3.0, 0.0, 1.0)
                i3 = brow + xx * 3
                img[i3] = int(img[i3] * (1.0 - w) + 7.0 * w)
                img[i3 + 1] = int(img[i3 + 1] * (1.0 - w) + 9.0 * w)
                img[i3 + 2] = int(img[i3 + 2] * (1.0 - w) + 18.0 * w)
    lamp_y = 0.806 * R
    # light beam, up and to the right toward the whale
    ox, oy = lx, lamp_y - 5.0
    dxn, dyn = 0.905, -0.426
    blen = 0.36 * R
    ex = ox + dxn * blen
    ey = oy + dyn * blen
    x0 = max(0, int(min(ox, ex) - 40))
    x1 = min(R - 1, int(max(ox, ex) + 40))
    y0 = max(0, int(min(oy, ey) - 40))
    y1 = min(R - 1, int(max(oy, ey) + 40))
    for yy in range(y0, y1 + 1):
        ry = yy - oy
        brow = yy * R * 3
        for xx in range(x0, x1 + 1):
            rx = xx - ox
            s = rx * dxn + ry * dyn
            if s <= 0.0 or s >= blen:
                continue
            perp = abs(-rx * dyn + ry * dxn)
            wdt = (3.0 + s * 0.030) * 2.2
            if perp >= wdt:
                continue
            w = ((1.0 - s / blen) ** 1.6) * (clamp(1.0 - perp / wdt, 0.0, 1.0) ** 2) * 0.34
            i3 = brow + xx * 3
            v = img[i3] + 255.0 * w
            img[i3] = 255 if v > 255 else int(v)
            v = img[i3 + 1] + 198.0 * w
            img[i3 + 1] = 255 if v > 255 else int(v)
            v = img[i3 + 2] + 102.0 * w
            img[i3 + 2] = 255 if v > 255 else int(v)
    # tower: a small tapered silhouette
    top_y = 0.820 * R
    bot_y = 0.902 * R
    for yy in range(int(top_y), int(bot_y)):
        f = (yy - top_y) / (bot_y - top_y)
        halfw = lerp(9.5, 16.5, f)
        brow = yy * R * 3
        for xx in range(int(lx - halfw), int(lx + halfw) + 1):
            cr, cg, cb = 19.0, 23.0, 39.0
            if xx > lx + halfw - 4.0:
                cr, cg, cb = 35.0, 43.0, 73.0
            i3 = brow + xx * 3
            img[i3] = int(cr)
            img[i3 + 1] = int(cg)
            img[i3 + 2] = int(cb)
    # gallery platform and lamp housing
    for yy in range(int(0.814 * R), int(0.820 * R)):
        brow = yy * R * 3
        for xx in range(int(lx - 15), int(lx + 15) + 1):
            i3 = brow + xx * 3
            img[i3] = 10
            img[i3 + 1] = 12
            img[i3 + 2] = 22
    for yy in range(int(lamp_y - 12), int(lamp_y + 2)):
        brow = yy * R * 3
        for xx in range(int(lx - 7), int(lx + 7) + 1):
            i3 = brow + xx * 3
            img[i3] = 12
            img[i3 + 1] = 13
            img[i3 + 2] = 20
    # the lamp itself: halo, then a bright core
    splat(img, lx, lamp_y - 5.0, 58.0, 255, 182, 84, 0.5)
    for yy in range(int(lamp_y - 9), int(lamp_y)):
        for xx in range(int(lx - 4), int(lx + 5)):
            if math.hypot(xx - lx, yy - (lamp_y - 5.0)) < 3.6:
                i3 = (yy * R + xx) * 3
                img[i3] = 255
                img[i3 + 1] = 214
                img[i3 + 2] = 120
    # one lit window, and a warm pool on the clouds below
    splat(img, lx, 0.862 * R, 2.2, 255, 176, 84, 0.9)
    splat(img, lx, 0.940 * R, 95.0, 205, 142, 60, 0.16)


# ------------------------------------------------------------------ finish
def finish(img):
    """Bloom from a bright pass, then 2x2 downsample with a vignette."""
    bs = 256
    bright = array("f", [0.0]) * (bs * bs * 3)
    for byy in range(bs):
        for bxx in range(bs):
            sr = sg = sb = 0.0
            for sy in range(byy * 8, byy * 8 + 8, 2):
                rb0 = sy * R * 3 + bxx * 24
                for sxo in range(0, 24, 6):
                    i3 = rb0 + sxo
                    sr += img[i3]
                    sg += img[i3 + 1]
                    sb += img[i3 + 2]
            idx = (byy * bs + bxx) * 3
            bright[idx] = max(0.0, sr * 0.0625 - 150.0) * 0.0095
            bright[idx + 1] = max(0.0, sg * 0.0625 - 150.0) * 0.0095
            bright[idx + 2] = max(0.0, sb * 0.0625 - 150.0) * 0.0095
    # two separable box-blur passes (radius 4)
    tmp = array("f", [0.0]) * (bs * bs * 3)
    for _ in range(2):
        for yy in range(bs):
            row = yy * bs * 3
            for ch in range(3):
                acc = 0.0
                for k in range(-4, 5):
                    acc += bright[row + clamp(k, 0, bs - 1) * 3 + ch]
                for xx in range(bs):
                    tmp[row + xx * 3 + ch] = acc / 9.0
                    xa = clamp(xx - 4, 0, bs - 1)
                    xb = clamp(xx + 5, 0, bs - 1)
                    acc += bright[row + xb * 3 + ch] - bright[row + xa * 3 + ch]
        for xx in range(bs):
            for ch in range(3):
                acc = 0.0
                for k in range(-4, 5):
                    acc += tmp[clamp(k, 0, bs - 1) * bs * 3 + xx * 3 + ch]
                for yy in range(bs):
                    bright[yy * bs * 3 + xx * 3 + ch] = acc / 9.0
                    ya = clamp(yy - 4, 0, bs - 1)
                    yb = clamp(yy + 5, 0, bs - 1)
                    acc += (tmp[yb * bs * 3 + xx * 3 + ch]
                            - tmp[ya * bs * 3 + xx * 3 + ch])
    # downsample
    out = bytearray(S * S * 3)
    xmap = []
    for x in range(S):
        gx = clamp((x + 0.5) * bs / S - 0.5, 0.0, bs - 1.001)
        ix = int(gx)
        xmap.append((ix, gx - ix))
    for y in range(S):
        gy = clamp((y + 0.5) * bs / S - 0.5, 0.0, bs - 1.001)
        iy = int(gy)
        fy = gy - iy
        dy = (y - S * 0.5) / (S * 0.5)
        dy2 = dy * dy
        srow0 = (2 * y) * R * 3
        srow1 = (2 * y + 1) * R * 3
        orow = y * S * 3
        brow0 = iy * bs * 3
        brow1 = (iy + 1) * bs * 3
        for x in range(S):
            ix, fx = xmap[x]
            dx = (x - S * 0.5) / (S * 0.5)
            vf = 1.0 - 0.30 * clamp((dx * dx + dy2 - 0.30) / 1.15, 0.0, 1.0)
            i00 = srow0 + x * 6
            i01 = srow1 + x * 6
            b00 = brow0 + ix * 3
            b10 = brow0 + (ix + 1) * 3
            b01 = brow1 + ix * 3
            b11 = brow1 + (ix + 1) * 3
            w00 = (1.0 - fx) * (1.0 - fy)
            w10 = fx * (1.0 - fy)
            w01 = (1.0 - fx) * fy
            w11 = fx * fy
            o3 = orow + x * 3
            for ch in range(3):
                basev = (img[i00 + ch] + img[i00 + 3 + ch]
                         + img[i01 + ch] + img[i01 + 3 + ch]) * 0.25
                bl = (bright[b00 + ch] * w00 + bright[b10 + ch] * w10
                      + bright[b01 + ch] * w01 + bright[b11 + ch] * w11)
                v = (basev + bl * 165.0 * 0.62) * vf
                out[o3 + ch] = 255 if v > 255 else (0 if v < 0 else int(v))
    return out


# ------------------------------------------------------------------ png
def write_png(path, w, h, rgb):
    w3 = w * 3
    table = bytes((b if b < 128 else 256 - b) for b in range(256))
    comp = zlib.compressobj(6, zlib.DEFLATED, zlib.MAX_WBITS)
    parts = []
    prev = bytes(w3)
    for y in range(h):
        row = bytes(rgb[y * w3:(y + 1) * w3])
        sub = row[:3] + bytes((a - b) & 0xFF
                              for a, b in zip(row[3:], row[:-3]))
        up = bytes((a - b) & 0xFF for a, b in zip(row, prev))
        s0 = sum(row.translate(table))
        s1 = sum(sub.translate(table))
        s2 = sum(up.translate(table))
        if s1 <= s0 and s1 <= s2:
            parts.append(b"\x01" + sub)
        elif s2 <= s0:
            parts.append(b"\x02" + up)
        else:
            parts.append(b"\x00" + row)
        prev = row
    idat = comp.compress(b"".join(parts)) + comp.flush()

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


# ------------------------------------------------------------------ main
def main():
    rng = Lcg(20261116)
    neb_a = make_noise(S, 150, 11)
    neb_b = make_noise(S, 42, 77)
    img = bytearray(R * R * 3)
    paint_sky(img, neb_a, neb_b)
    paint_stars(img, rng)
    paint_moon(img, neb_b)
    spine = build_spine()
    sdf, wu, wv = build_whale_field(spine)
    paint_whale(img, sdf, wu, wv, spine, rng, neb_b)
    paint_belly_droplets(img, spine, rng)
    by = cloud_top()
    paint_clouds(img, neb_b, by, rng)
    paint_breach(img, by, rng)
    paint_lighthouse(img)
    out = finish(img)
    os.makedirs("/output", exist_ok=True)
    write_png(OUT, S, S, out)


if __name__ == "__main__":
    main()

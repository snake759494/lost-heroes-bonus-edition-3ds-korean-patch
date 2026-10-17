using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

// MobiClip (moflex) video decoder + residual transcoder.
// Ported from FFmpeg libavcodec/mobiclip.c (LGPL) semantics.

class BitR {
    byte[] b; int pos; int nbits;
    public BitR(byte[] pkt) {
        int n = (pkt.Length + 1) & ~1;
        b = new byte[n + 8];
        for (int i = 0; i < pkt.Length; i++) b[i ^ 1] = pkt[i];
        nbits = n * 8;
    }
    public int Left => nbits - pos;
    public int Bit() { int v = (b[pos >> 3] >> (7 - (pos & 7))) & 1; pos++; return v; }
    public int Bits(int n) { int v = 0; for (int i = 0; i < n; i++) v = (v << 1) | Bit(); return v; }
    public int SBits(int n) { int v = Bits(n); if ((v & (1 << (n - 1))) != 0) v -= 1 << n; return v; }
    public int UE() { int z = 0; while (Bit() == 0) { z++; if (z > 31) throw new Exception("ue"); } return (1 << z) - 1 + Bits(z); }
    public int SE() { int v = UE(); return (v & 1) != 0 ? (v + 1) >> 1 : -(v >> 1); }
}

class BitW {
    public List<byte> bits = new List<byte>();
    public void Bit(int v) { bits.Add((byte)(v & 1)); }
    public void Bits(int v, int n) { for (int i = n - 1; i >= 0; i--) bits.Add((byte)((v >> i) & 1)); }
    public void UE(int v) { int x = v + 1; int len = 0; while ((x >> len) > 1) len++; for (int i = 0; i < len; i++) bits.Add(0); Bits(x, len + 1); }
    public void SE(int v) { UE(v > 0 ? 2 * v - 1 : -2 * v); }
    public void Append(BitW o) { bits.AddRange(o.bits); }
    public int Count => bits.Count;
    public byte[] ToBytes(int padTo) {
        int nb = (bits.Count + 7) / 8; if (nb % 2 == 1) nb++;
        int total = Math.Max(nb, padTo); if (total % 2 == 1) total++;
        var raw = new byte[total];
        for (int i = 0; i < bits.Count; i++) if (bits[i] != 0) raw[i >> 3] |= (byte)(0x80 >> (i & 7));
        var outb = new byte[total];
        for (int i = 0; i < total; i++) outb[i ^ 1] = raw[i];
        return outb;
    }
}

class Vlc {
    public Dictionary<(int, int), int> dec = new();   // (len,code)->sym
    public Dictionary<int, (int code, int len)> enc = new();
    public int maxLen;
    public Vlc(byte[] lens, int[] syms) {
        uint code = 0;
        for (int i = 0; i < lens.Length; i++) {
            int len = lens[i];
            int c = (int)(code >> (32 - len));
            dec[(len, c)] = syms[i];
            if (!enc.ContainsKey(syms[i]) || enc[syms[i]].len > len) enc[syms[i]] = (c, len);
            code += 1u << (32 - len);
            maxLen = Math.Max(maxLen, len);
        }
    }
    public int Read(BitR r) {
        int c = 0;
        for (int len = 1; len <= maxLen; len++) {
            c = (c << 1) | r.Bit();
            if (dec.TryGetValue((len, c), out int s)) return s;
        }
        throw new Exception("vlc");
    }
    public void Write(BitW w, int sym) { var e = enc[sym]; w.Bits(e.code, e.len); }
}

class Plane {
    public int w, h; public byte[] d;
    public Plane(int w, int h) { this.w = w; this.h = h; d = new byte[w * h]; }
    public Plane Clone() { var p = new Plane(w, h); Array.Copy(d, p.d, d.Length); return p; }
}
class Pic {
    public Plane[] p = new Plane[3];
    public Pic(int w, int h) { p[0] = new Plane(w, h); p[1] = new Plane(w / 2, h / 2); p[2] = new Plane(w / 2, h / 2); }
    public Pic Clone() { var c = new Pic(1, 1); for (int i = 0; i < 3; i++) c.p[i] = p[i].Clone(); return c; }
}

static class T {
    public static readonly byte[] zigzag4 = { 0x00, 0x04, 0x01, 0x02, 0x05, 0x08, 0x0C, 0x09, 0x06, 0x03, 0x07, 0x0A, 0x0D, 0x0E, 0x0B, 0x0F };
    public static readonly byte[] zigzag8 = {
        0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
        35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63 };
    public static readonly byte[,] quant4 = {
        { 10, 13, 13, 10, 16, 10, 13, 13, 13, 13, 16, 10, 16, 13, 13, 16 },
        { 11, 14, 14, 11, 18, 11, 14, 14, 14, 14, 18, 11, 18, 14, 14, 18 },
        { 13, 16, 16, 13, 20, 13, 16, 16, 16, 16, 20, 13, 20, 16, 16, 20 },
        { 14, 18, 18, 14, 23, 14, 18, 18, 18, 18, 23, 14, 23, 18, 18, 23 },
        { 16, 20, 20, 16, 25, 16, 20, 20, 20, 20, 25, 16, 25, 20, 20, 25 },
        { 18, 23, 23, 18, 29, 18, 23, 23, 23, 23, 29, 18, 29, 23, 23, 29 } };
    public static readonly byte[][] quant8 = {
        new byte[]{ 20, 19, 19, 25, 18, 25, 19, 24, 24, 19, 20, 18, 32, 18, 20, 19, 19, 24, 24, 19, 19, 25, 18, 25, 18, 25, 18, 25, 19, 24, 24, 19, 19, 24, 24, 19, 18, 32, 18, 20, 18, 32, 18, 24, 24, 19, 19, 24, 24, 18, 25, 18, 25, 18, 19, 24, 24, 19, 18, 32, 18, 24, 24, 18 },
        new byte[]{ 22, 21, 21, 28, 19, 28, 21, 26, 26, 21, 22, 19, 35, 19, 22, 21, 21, 26, 26, 21, 21, 28, 19, 28, 19, 28, 19, 28, 21, 26, 26, 21, 21, 26, 26, 21, 19, 35, 19, 22, 19, 35, 19, 26, 26, 21, 21, 26, 26, 19, 28, 19, 28, 19, 21, 26, 26, 21, 19, 35, 19, 26, 26, 19 },
        new byte[]{ 26, 24, 24, 33, 23, 33, 24, 31, 31, 24, 26, 23, 42, 23, 26, 24, 24, 31, 31, 24, 24, 33, 23, 33, 23, 33, 23, 33, 24, 31, 31, 24, 24, 31, 31, 24, 23, 42, 23, 26, 23, 42, 23, 31, 31, 24, 24, 31, 31, 23, 33, 23, 33, 23, 24, 31, 31, 24, 23, 42, 23, 31, 31, 23 },
        new byte[]{ 28, 26, 26, 35, 25, 35, 26, 33, 33, 26, 28, 25, 45, 25, 28, 26, 26, 33, 33, 26, 26, 35, 25, 35, 25, 35, 25, 35, 26, 33, 33, 26, 26, 33, 33, 26, 25, 45, 25, 28, 25, 45, 25, 33, 33, 26, 26, 33, 33, 25, 35, 25, 35, 25, 26, 33, 33, 26, 25, 45, 25, 33, 33, 25 },
        new byte[]{ 32, 30, 30, 40, 28, 40, 30, 38, 38, 30, 32, 28, 51, 28, 32, 30, 30, 38, 38, 30, 30, 40, 28, 40, 28, 40, 28, 40, 30, 38, 38, 30, 30, 38, 38, 30, 28, 51, 28, 32, 28, 51, 28, 38, 38, 30, 30, 38, 38, 28, 40, 28, 40, 28, 30, 38, 38, 30, 28, 51, 28, 38, 38, 28 },
        new byte[]{ 36, 34, 34, 46, 32, 46, 34, 43, 43, 34, 36, 32, 58, 32, 36, 34, 34, 43, 43, 34, 34, 46, 32, 46, 32, 46, 32, 46, 34, 43, 43, 34, 34, 43, 43, 34, 32, 58, 32, 36, 32, 58, 32, 43, 43, 34, 34, 43, 43, 32, 46, 32, 46, 32, 34, 43, 43, 34, 32, 58, 32, 43, 43, 32 } };
    public static readonly int[] blk4 = { 15, 0, 2, 1, 4, 8, 12, 3, 11, 13, 14, 7, 10, 5, 9, 6 };
    public static readonly int[] pblk4 = { 0, 4, 1, 8, 2, 12, 3, 5, 10, 15, 7, 13, 14, 11, 9, 6 };
    public static readonly int[] blk8 = {
        0x00, 0x1F, 0x3F, 0x0F, 0x08, 0x04, 0x02, 0x01, 0x0B, 0x0E, 0x1B, 0x0D, 0x03, 0x07, 0x0C, 0x17, 0x1D, 0x0A, 0x1E, 0x05, 0x10, 0x2F, 0x37, 0x3B,
        0x13, 0x3D, 0x3E, 0x09, 0x1C, 0x06, 0x15, 0x1A, 0x33, 0x11, 0x12, 0x14, 0x18, 0x20, 0x3C, 0x35, 0x19, 0x16, 0x3A, 0x30, 0x31, 0x32, 0x27, 0x34,
        0x2B, 0x2D, 0x39, 0x38, 0x23, 0x36, 0x2E, 0x21, 0x25, 0x22, 0x24, 0x2C, 0x2A, 0x28, 0x29, 0x26 };
    public static readonly int[] pblk8 = {
        0x00, 0x0F, 0x04, 0x01, 0x08, 0x02, 0x0C, 0x03, 0x05, 0x0A, 0x0D, 0x07, 0x0E, 0x0B, 0x1F, 0x09, 0x06, 0x10, 0x3F, 0x1E, 0x17, 0x1D, 0x1B, 0x1C, 0x13, 0x18, 0x1A, 0x12, 0x11, 0x14, 0x15, 0x20,
        0x2F, 0x16, 0x19, 0x37, 0x3D, 0x3E, 0x3B, 0x3C, 0x33, 0x35, 0x21, 0x24, 0x22, 0x28, 0x23, 0x2C, 0x30, 0x27, 0x2D, 0x25, 0x3A, 0x2B, 0x2E, 0x2A, 0x31, 0x34, 0x38, 0x32, 0x29, 0x26, 0x39, 0x36 };
    public static readonly byte[,] runres = {
      { 12,6,4,3,3,3,3,2,2,2,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        3,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        1,27,11,7,3,2,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
        1,41,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1 },
      { 27,10,5,4,3,3,3,3,2,2,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        8,3,2,2,2,2,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        1,15,10,8,4,3,2,2,2,2,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
        1,21,7,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1 } };
    public static readonly byte[] bits0 = {
        9,11,11,11,11,10,10,10,10,10,10,10,10,10,10, 10,10,11,11,11,11,11,11,11,11,12,12,12,12,12, 12,12,12,12,12,12,12,12,12,12,12,7,10,10,9,
        9,9,9,9,9,9,9,9,9,9,9,9,9,9,9, 9,9,9,9,9,8,8,8,8,8,8,8,8,8,8, 8,8,8,7,7,7,7,7,7,7,7,6,6,6,6, 6,6,6,6,6,6,5,5,5,4,2,3,4,4 };
    public static readonly int[] syms0 = {
        0x0,0x822,0x803,0xB,0xA,0xB81,0xB61,0xB41,0xB21,0x122, 0x102,0xE2,0xC2,0xA2,0x63,0x43,0x24,0xC,0x25,0x2E1,0x301,
        0xBA1,0xBC1,0xBE1,0xC01,0x26,0x44,0x83,0xA3,0xC3,0x142, 0x321,0x341,0xC21,0xC41,0xC61,0xC81,0xCA1,0xCC1,0xCE1,0xD01,
        0x0,0x9,0x8,0xB01,0xAE1,0xAC1,0xAA1,0xA81,0xA61,0xA41,0xA21, 0x802,0x2C1,0x2A1,0x281,0x261,0x241,0x221,0x201,0x1E1,0x82,
        0x62,0x7,0x6,0xA01,0x9E1,0x9C1,0x9A1,0x981,0x961,0x941,0x921, 0x1C1,0x1A1,0x42,0x23,0x5,0x901,0x8E1,0x8C1,0x8A1,0x181,0x161,
        0x141,0x4,0x881,0x861,0x841,0x821,0x121,0x101,0xE1,0xC1,0x22, 0x3,0xA1,0x81,0x61,0x801,0x1,0x21,0x41,0x2 };
    public static readonly int[] syms1 = {
        0x0,0x807,0x806,0x16,0x15,0x842,0x823,0x805,0x1A1,0xA3,0x102,0x83, 0x64,0x44,0x27,0x14,0x13,0x17,0x18,0x28,0x122,0x862,0x882,0x9E1,0xA01,
        0x19,0x1A,0x1B,0x29,0xC3,0x2A,0x45,0xE3,0x1C1,0x808,0x8A2,0x8C2,0xA21, 0xA41,0xA61,0xA81,0x0,0x12,0x11,0x9C1,0x9A1,0x981,0x961,0x941,0x822,0x804,
        0x181,0x161,0xE2,0xC2,0xA2,0x63,0x43,0x26,0x25,0x10,0x82,0xF,0xE,0xD,0x901, 0x8E1,0x8C1,0x803,0x141,0x121,0x101,0x921,0x62,0x24,0xC,0xB,0xA,0x881,0x861,
        0xC1,0x8A1,0xE1,0x42,0x23,0x9,0x802,0xA1,0x841,0x821,0x81,0x61,0x8,0x7,0x22, 0x6,0x41,0x5,0x4,0x801,0x1,0x2,0x21,0x3 };
    public static readonly byte[] mvlen = { 10, 8, 8, 7, 8, 8, 8, 7, 8, 8, 8, 7, 7, 7, 7, 6 };
    public static readonly byte[][][] mvbits = {
      new byte[][]{ new byte[]{2,3,3,5,5,4,4,5,5,2}, new byte[]{2,3,4,4,3,4,4,2}, new byte[]{3,4,4,2,4,4,3,2}, new byte[]{1,3,4,5,5,3,3}, new byte[]{2,4,4,3,3,4,4,2}, new byte[]{2,3,4,4,4,4,3,2}, new byte[]{2,3,4,4,4,4,3,2}, new byte[]{2,2,3,4,5,5,2},
                    new byte[]{2,3,4,4,3,4,4,2}, new byte[]{2,4,4,3,4,4,3,2}, new byte[]{2,3,3,5,5,4,3,2}, new byte[]{2,3,4,4,3,3,2}, new byte[]{1,4,4,3,3,4,4}, new byte[]{2,3,4,4,3,3,2}, new byte[]{2,3,4,4,3,3,2}, new byte[]{3,3,2,2,3,3} },
      new byte[][]{ new byte[]{3,4,5,5,3,5,6,6,4,1}, new byte[]{2,3,4,5,5,2,3,3}, new byte[]{2,4,4,3,3,4,4,2}, new byte[]{1,4,4,3,4,4,3}, new byte[]{3,3,2,4,5,5,3,2}, new byte[]{3,4,4,3,3,3,3,2}, new byte[]{1,3,3,4,4,4,5,5}, new byte[]{1,4,4,3,3,4,4},
                    new byte[]{2,4,4,3,3,4,4,2}, new byte[]{1,3,3,4,4,4,5,5}, new byte[]{2,3,4,4,4,4,3,2}, new byte[]{2,3,3,4,4,3,2}, new byte[]{1,4,4,3,3,4,4}, new byte[]{1,4,4,3,3,4,4}, new byte[]{2,3,3,4,4,3,2}, new byte[]{2,3,3,3,3,2} } };
    public static readonly int[][][] mvsyms = {
      new int[][]{ new[]{1,8,9,4,3,2,7,5,6,0}, new[]{0,9,5,4,2,3,8,1}, new[]{3,9,5,0,4,8,2,1}, new[]{1,3,4,8,5,2,0}, new[]{0,5,4,8,2,3,9,1}, new[]{0,3,5,9,4,8,2,1}, new[]{0,3,9,5,8,4,2,1}, new[]{0,2,3,4,8,5,1},
                   new[]{0,3,8,4,2,5,9,1}, new[]{2,8,9,3,5,4,0,1}, new[]{0,4,3,8,9,5,2,1}, new[]{0,4,8,5,3,2,1}, new[]{1,9,4,2,0,5,3}, new[]{2,4,9,5,3,0,1}, new[]{0,4,9,5,3,2,1}, new[]{5,4,1,0,3,2} },
      new int[][]{ new[]{8,2,3,6,1,7,5,4,9,0}, new[]{9,2,3,5,4,1,8,0}, new[]{0,5,4,2,9,3,8,1}, new[]{1,5,4,2,8,3,0}, new[]{2,9,8,3,5,4,0,1}, new[]{3,5,4,2,9,8,0,1}, new[]{1,2,0,9,8,3,5,4}, new[]{1,8,5,2,0,4,3},
                   new[]{0,5,4,2,8,3,9,1}, new[]{1,2,0,9,8,3,5,4}, new[]{0,3,9,8,5,4,2,1}, new[]{0,4,3,8,5,2,1}, new[]{1,5,4,2,0,9,3}, new[]{1,9,5,2,0,4,3}, new[]{0,5,3,9,4,2,1}, new[]{0,4,5,3,2,1} } };
}

class Mobi {
    public int W, H;
    public Pic[] pics = new Pic[6];
    public int cur;
    int moflex, dctIdx, quant;
    int[][] qtab = { new int[64], new int[64] };
    int[] pre = new int[32];
    int[] mx, my, omx, omy;
    Vlc[] rl = new Vlc[2];
    Vlc[,] mv = new Vlc[2, 16];
    // transcode state
    BitR R; BitW Wt;              // Wt: current output writer (null = pure decode)
    Pic target;                    // target image when transcoding
    public double deadzone = 0.30;
    public bool transcode => Wt != null || tmode;
    bool tmode;
    public int lastQuant => quant;

    public Mobi(int w, int h) {
        W = w; H = h;
        for (int i = 0; i < 6; i++) pics[i] = new Pic(w, h);
        mx = new int[w / 16 + 3]; my = new int[w / 16 + 3]; omx = new int[w / 16 + 3]; omy = new int[w / 16 + 3];
        rl[0] = new Vlc(T.bits0, T.syms0); rl[1] = new Vlc(T.bits0, T.syms1);
        for (int i = 0; i < 2; i++) for (int j = 0; j < 16; j++) mv[i, j] = new Vlc(T.mvbits[i][j], T.mvsyms[i][j]);
        BuildBases();
    }
    public Mobi CloneState() {
        var m = (Mobi)MemberwiseClone();
        m.pics = pics.Select(p => p.Clone()).ToArray();
        m.qtab = new[] { (int[])qtab[0].Clone(), (int[])qtab[1].Clone() };
        m.pre = (int[])pre.Clone(); m.mx = (int[])mx.Clone(); m.my = (int[])my.Clone(); m.omx = (int[])omx.Clone(); m.omy = (int[])omy.Clone();
        return m;
    }

    void SetupQ(int q) {
        if (q < 12 || q > 161) throw new Exception("quant " + q);
        quant = q; int qx = q % 6, qy = q / 6;
        for (int i = 0; i < 16; i++) qtab[0][i] = T.quant4[qx, i] << qy;
        for (int i = 0; i < 64; i++) qtab[1][i] = T.quant8[qx][i] << (qy - 2);
        for (int i = 0; i < 20; i++) pre[i] = 9;
    }

    // ---------- syntax copy helpers ----------
    BitW O => Wt;
    int CBits(int n) { int v = R.Bits(n); O?.Bits(v, n); return v; }
    int CBit() { int v = R.Bit(); O?.Bit(v); return v; }
    int CUE() { int v = R.UE(); O?.UE(v); return v; }
    int CSE() { int v = R.SE(); O?.SE(v); return v; }
    int CMV(int t) { int v = mv[moflex, t].Read(R); if (O != null) mv[moflex, t].Write(O, v); return v; }

    // ---------- IDCT ----------
    static void Inv4(int[] a, int o) {
        int A = a[o] + a[o + 2], B = a[o] - a[o + 2], C = a[o + 1] + (a[o + 3] >> 1), D = (a[o + 1] >> 1) - a[o + 3];
        a[o] = A + C; a[o + 1] = B + D; a[o + 2] = B - D; a[o + 3] = A - C;
    }
    static void Idct(int[] arr, int o, int size) {
        if (size == 4) { Inv4(arr, o); return; }
        int[] tmp = { arr[o], arr[o + 2], arr[o + 4], arr[o + 6] };
        Inv4(tmp, 0);
        int e = arr[o + 7] + arr[o + 1] - arr[o + 3] - (arr[o + 3] >> 1);
        int f = arr[o + 7] - arr[o + 1] + arr[o + 5] + (arr[o + 5] >> 1);
        int g = arr[o + 5] - arr[o + 3] - arr[o + 7] - (arr[o + 7] >> 1);
        int h = arr[o + 5] + arr[o + 3] + arr[o + 1] + (arr[o + 1] >> 1);
        int x3 = g + (h >> 2), x2 = e + (f >> 2), x1 = (e >> 2) - f, x0 = h - (g >> 2);
        arr[o] = tmp[0] + x0; arr[o + 1] = tmp[1] + x1; arr[o + 2] = tmp[2] + x2; arr[o + 3] = tmp[3] + x3;
        arr[o + 4] = tmp[3] - x3; arr[o + 5] = tmp[2] - x2; arr[o + 6] = tmp[1] - x1; arr[o + 7] = tmp[0] - x0;
    }
    static void ApplyMat(int[] mat, int size, Plane pl, int bx, int by) {
        mat[0] += 32;
        for (int y = 0; y < size; y++) Idct(mat, y * size, size);
        for (int y = 0; y < size; y++) {
            for (int x = y + 1; x < size; x++) { int a = mat[x * size + y], b = mat[y * size + x]; mat[y * size + x] = a; mat[x * size + y] = b; }
            Idct(mat, y * size, size);
            int row = (by + y) * pl.w + bx;
            for (int x = 0; x < size; x++) { int v = pl.d[row + x] + (mat[y * size + x] >> 6); pl.d[row + x] = (byte)(v < 0 ? 0 : v > 255 ? 255 : v); }
        }
    }
    // float bases for forward transform
    double[][,] basis4 = new double[16][,], basis8 = new double[64][,];
    double[] bnorm4 = new double[16], bnorm8 = new double[64];
    static void Inv4F(double[] a, int o) {
        double A = a[o] + a[o + 2], B = a[o] - a[o + 2], C = a[o + 1] + a[o + 3] / 2, D = a[o + 1] / 2 - a[o + 3];
        a[o] = A + C; a[o + 1] = B + D; a[o + 2] = B - D; a[o + 3] = A - C;
    }
    static void IdctF(double[] arr, int o, int size) {
        if (size == 4) { Inv4F(arr, o); return; }
        double[] tmp = { arr[o], arr[o + 2], arr[o + 4], arr[o + 6] };
        Inv4F(tmp, 0);
        double e = arr[o + 7] + arr[o + 1] - arr[o + 3] - arr[o + 3] / 2, f = arr[o + 7] - arr[o + 1] + arr[o + 5] + arr[o + 5] / 2;
        double g = arr[o + 5] - arr[o + 3] - arr[o + 7] - arr[o + 7] / 2, h = arr[o + 5] + arr[o + 3] + arr[o + 1] + arr[o + 1] / 2;
        double x3 = g + h / 4, x2 = e + f / 4, x1 = e / 4 - f, x0 = h - g / 4;
        arr[o] = tmp[0] + x0; arr[o + 1] = tmp[1] + x1; arr[o + 2] = tmp[2] + x2; arr[o + 3] = tmp[3] + x3;
        arr[o + 4] = tmp[3] - x3; arr[o + 5] = tmp[2] - x2; arr[o + 6] = tmp[1] - x1; arr[o + 7] = tmp[0] - x0;
    }
    void BuildBases() {
        foreach (int size in new[] { 4, 8 }) {
            int n = size * size;
            for (int k = 0; k < n; k++) {
                var m = new double[n]; m[k] = 1;
                for (int y = 0; y < size; y++) IdctF(m, y * size, size);
                var t = new double[n];
                for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) t[y * size + x] = m[x * size + y];
                for (int y = 0; y < size; y++) IdctF(t, y * size, size);
                var B = new double[size, size]; double nn = 0;
                for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) { B[y, x] = t[y * size + x] / 64.0; nn += B[y, x] * B[y, x]; }
                if (size == 4) { basis4[k] = B; bnorm4[k] = nn; } else { basis8[k] = B; bnorm8[k] = nn; }
            }
        }
    }

    // ---------- coefficients ----------
    // reads original coefficients; returns zigzag-ordered levels. apply=true adds to recon (decode mode)
    int[] SkipOrApplyCoeffs(int bx, int by, int size, int plane, bool apply) {
        var lv = new int[size * size];
        for (int pos = 0; R.Left > 0; pos++) {
            int n = rl[dctIdx].Read(R);
            int last = (n >> 11) == 1 ? 1 : 0, run = (n >> 5) & 0x3F, level = n & 0x1F;
            if (level != 0) { if (R.Bit() == 1) level = -level; }
            else if (R.Bit() == 0) {
                n = rl[dctIdx].Read(R); last = (n >> 11) == 1 ? 1 : 0; run = (n >> 5) & 0x3F; level = n & 0x1F;
                level += T.runres[dctIdx, (last != 0 ? 64 : 0) + run];
                if (R.Bit() == 1) level = -level;
            } else if (R.Bit() == 0) {
                n = rl[dctIdx].Read(R); last = (n >> 11) == 1 ? 1 : 0; run = (n >> 5) & 0x3F; level = n & 0x1F;
                run += T.runres[dctIdx, 128 + (last != 0 ? 64 : 0) + level];
                if (R.Bit() == 1) level = -level;
            } else { last = R.Bit(); run = R.Bits(6); level = R.SBits(12); }
            pos += run;
            if (pos >= size * size) throw new Exception("coef pos");
            lv[pos] = level;
            if (last != 0) break;
        }
        if (apply) ApplyLevels(lv, size, plane, bx, by, pics[cur]);
        return lv;
    }
    void ApplyLevels(int[] lv, int size, int plane, int bx, int by, Pic pic) {
        var mat = new int[64]; var ztab = size == 8 ? T.zigzag8 : T.zigzag4; var q = qtab[size == 8 ? 1 : 0];
        for (int pos = 0; pos < size * size; pos++) if (lv[pos] != 0) mat[ztab[pos]] = q[pos] * lv[pos];
        ApplyMat(mat, size, pic.p[plane], bx, by);
    }
    void WriteLevels(BitW w, int[] lv, int size) {
        int n = size * size; int lastpos = -1; for (int pos = 0; pos < n; pos++) if (lv[pos] != 0) lastpos = pos;
        int prev = -1; var tab = rl[dctIdx];
        for (int pos = 0; pos <= lastpos; pos++) {
            if (lv[pos] == 0) continue;
            int run = pos - prev - 1; prev = pos;
            int last = pos == lastpos ? 1 : 0; int level = lv[pos]; int al = Math.Abs(level);
            int sym = (last << 11) | (run << 5) | al;
            int sg = level < 0 ? 1 : 0;
            if (al < 32 && tab.enc.ContainsKey(sym)) { tab.Write(w, sym); w.Bit(sg); continue; }
            var esc = tab.enc[0];
            int best = 1 << 30, mode = -1, bsym = 0;
            // mode A: level offset
            int la = al - T.runres[dctIdx, (last != 0 ? 64 : 0) + run];
            if (la > 0 && la < 32) { int sa = (last << 11) | (run << 5) | la; if (tab.enc.ContainsKey(sa)) { int c = esc.len + 1 + tab.enc[sa].len + 1; if (c < best) { best = c; mode = 0; bsym = sa; } } }
            // mode B: run offset
            if (al < 32 && al < 64) {
                int rb = run - T.runres[dctIdx, 128 + (last != 0 ? 64 : 0) + al];
                if (rb >= 0) { int sb = (last << 11) | (rb << 5) | al; if (tab.enc.ContainsKey(sb)) { int c = esc.len + 2 + tab.enc[sb].len + 1; if (c < best) { best = c; mode = 1; bsym = sb; } } }
            }
            if (esc.len + 2 + 1 + 6 + 12 < best) mode = 2;
            w.Bits(esc.code, esc.len);
            if (mode == 0) { w.Bit(0); tab.Write(w, bsym); w.Bit(sg); }
            else if (mode == 1) { w.Bit(1); w.Bit(0); tab.Write(w, bsym); w.Bit(sg); }
            else { w.Bit(1); w.Bit(1); w.Bit(last); w.Bits(run, 6); w.Bits(level & 0xFFF, 12); }
        }
    }
    static bool AnyNZ(int[] lv) { if (lv == null) return false; foreach (var v in lv) if (v != 0) return true; return false; }
    public Pic origPic; public int origQ;
    int[] OrigQtab(int size) { int qx = origQ % 6, qy = origQ / 6; var t = new int[size * size]; for (int i = 0; i < t.Length; i++) t[i] = size == 4 ? T.quant4[qx, i] << qy : T.quant8[qx][i] << (qy - 2); return t; }
    int[] Rescale(int[] lv, int size) {
        if (lv != null && trimPos < 999) {
            int tp = size == 8 ? trimPos : Math.Max(3, trimPos / 4);
            var c = (int[])lv.Clone(); for (int i = tp; i < c.Length; i++) if (Math.Abs(c[i]) <= 1) c[i] = 0;
            lv = c;
        }
        if (lv == null || quant == origQ) return lv;
        var oq = OrigQtab(size); var nq = qtab[size == 8 ? 1 : 0]; var r = new int[lv.Length];
        for (int i = 0; i < lv.Length; i++) if (lv[i] != 0) r[i] = (int)Math.Round(lv[i] * (double)oq[i] / nq[i]);
        return r;
    }
    bool Changed(int bx, int by, int size, int plane) {
        var t = target.p[plane]; var o = origPic.p[plane];
        for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) { int k = (by + y) * t.w + bx + x; if (t.d[k] != o.d[k]) return true; }
        return false;
    }
    double SimErr(int[] lv, int bx, int by, int size, int plane, out int maxe) {
        var pl = pics[cur].p[plane]; var tg = target.p[plane];
        var tmp = new Pic(2, 2); var cp = new Plane(pl.w, pl.h); tmp.p[plane] = cp;
        for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) { int k = (by + y) * pl.w + bx + x; cp.d[k] = pl.d[k]; }
        if (AnyNZ(lv)) ApplyLevels(lv, size, plane, bx, by, tmp);
        double e = 0; maxe = 0;
        for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) { int k = (by + y) * pl.w + bx + x; int d = Math.Abs(cp.d[k] - tg.d[k]); e += d; if (d > maxe) maxe = d; }
        return e / (size * size);
    }
    int[] Quantize(int bx, int by, int size, int plane) {
        var pl = pics[cur].p[plane]; var tg = target.p[plane];
        var q = qtab[size == 8 ? 1 : 0];
        var bas = size == 8 ? basis8 : basis4; var bn = size == 8 ? bnorm8 : bnorm4; var ztab = size == 8 ? T.zigzag8 : T.zigzag4;
        int n = size * size; var r = new double[size, size];
        for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) r[y, x] = tg.d[(by + y) * pl.w + bx + x] - pl.d[(by + y) * pl.w + bx + x];
        var lv = new int[n]; bool any = false;
        for (int pos = 0; pos < n; pos++) {
            int k = ztab[pos]; var B = bas[k];
            double dot = 0; for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) dot += r[y, x] * B[y, x];
            double c = dot / bn[k] / q[pos];
            int l = (int)Math.Floor(Math.Abs(c) + 0.5 - deadzone); if (l > 2047) l = 2047; if (c < 0) l = -l;
            if (pos >= (size == 8 ? hfCap : Math.Max(4, hfCap / 4))) l = 0;
            lv[pos] = l; if (l != 0) any = true;
        }
        return any ? lv : null;
    }
    public double reuseThr = 1.5; public int reuseMax = 14; public int hfCap = 64; public double zeroBias = 0.9; public int trimPos = 999; public static int nReuse, nQuant, nChanged;
    int[] Decide(int bx, int by, int size, int plane, int[] origLv) {
        if (!Changed(bx, by, size, plane)) {
            var cand = Rescale(origLv, size);
            double e = SimErr(cand, bx, by, size, plane, out int mx_);
            if (e <= reuseThr && mx_ <= reuseMax) { nReuse++; return AnyNZ(cand) ? cand : null; }
        } else nChanged++;
        nQuant++;
        return Quantize(bx, by, size, plane);
    }
    bool EncodeBlock(BitW w, int bx, int by, int size, int plane, int[] origLv) {
        var lv = Decide(bx, by, size, plane, origLv);
        if (!AnyNZ(lv)) return false;
        ApplyLevels(lv, size, plane, bx, by, pics[cur]);
        WriteLevels(w, lv, size);
        return true;
    }

    // ---------- intra prediction ----------
    struct BXY { public int w, h, ax, ay, x, y, size; public Plane pl; }
    static int Pget(BXY b) {
        int rx = b.x, ry = b.y;
        if (b.x == -1 && b.y >= b.size) { rx = -1; ry = b.size - 1; }
        else if (b.x >= -1 && b.y >= -1) { }
        else if (b.x == -1 && b.y == -2) { rx = 0; ry = -1; }
        else if (b.x == -2 && b.y == -1) { rx = -1; ry = 0; }
        int y = Math.Clamp(b.ay + ry, 0, b.h - 1), x = Math.Clamp(b.ax + rx, 0, b.w - 1);
        return b.pl.d[y * b.pl.w + x];
    }
    static int Half(int a, int b) => ((a + b) + 1) / 2;
    static int Half3(int a, int b, int c) => ((a + b + b + c) * 2 / 4 + 1) / 2;
    static int PickAbove(BXY b) { b.y -= 1; return Pget(b); }
    static int PickLeft(BXY b) { b.x -= 1; return Pget(b); }
    static int HalfHorz(BXY b) { var a = b; var c = b; a.x -= 1; c.x += 1; return Half3(Pget(a), Pget(b), Pget(c)); }
    static int HalfVert(BXY b) { var a = b; var c = b; a.y -= 1; c.y += 1; return Half3(Pget(a), Pget(b), Pget(c)); }
    static int Pick4(BXY b) {
        if ((b.x % 2) == 0) { var ba = b; ba.x = -1; ba.y = b.y + b.x / 2; int a = Pget(ba); var bb = b; bb.x = -1; bb.y = b.y + b.x / 2 + 1; return Half(a, Pget(bb)); }
        else { var ba = b; ba.x = -1; ba.y = b.y + b.x / 2 + 1; return HalfVert(ba); }
    }
    static int Pick5(BXY b) {
        if (b.x == 0) { var a = b; var c = b; a.x = -1; a.y -= 1; c.x = -1; return Half(Pget(a), Pget(c)); }
        else if (b.y == 0) { var a = b; a.x -= 2; a.y -= 1; return HalfHorz(a); }
        else if (b.x == 1) { var a = b; a.x -= 2; a.y -= 1; return HalfVert(a); }
        else { var a = b; a.x -= 2; a.y -= 1; return Pget(a); }
    }
    static int Pick6(BXY b) {
        if (b.y == 0) { var a = b; var c = b; a.x -= 1; a.y = -1; c.y = -1; return Half(Pget(a), Pget(c)); }
        else if (b.x == 0) { var a = b; a.x -= 1; a.y -= 2; return HalfVert(a); }
        else if (b.y == 1) { var a = b; a.x -= 1; a.y -= 2; return HalfHorz(a); }
        else { var a = b; a.x -= 1; a.y -= 2; return Pget(a); }
    }
    static int Pick7(BXY b) {
        var a = b; a.x -= 1; a.y -= 1; int clr = Pget(a);
        if (b.x != 0 && b.y != 0) return clr;
        if (b.x == 0) { a.x = -1; a.y = b.y; } else { a.x = b.x - 2; a.y = -1; }
        int acc1 = Pget(a);
        if (b.y == 0) { a.x = b.x; a.y = -1; } else { a.x = -1; a.y = b.y - 2; }
        int acc2 = Pget(a);
        return Half3(acc1, clr, acc2);
    }
    static int Pick8(BXY b) {
        var ba = b; var bb = b;
        if (b.y == 0) { ba.y = -1; int a = Pget(ba); bb.x += 1; bb.y = -1; return Half(a, Pget(bb)); }
        else if (b.y == 1) { ba.x += 1; ba.y -= 2; return HalfHorz(ba); }
        else if (b.x < b.size - 1) { ba.x += 1; ba.y -= 2; return Pget(ba); }
        else if (b.y % 2 == 0) { ba.x = b.y / 2 + b.size - 1; ba.y = -1; int a = Pget(ba); bb.x = b.y / 2 + b.size; bb.y = -1; return Half(a, Pget(bb)); }
        else { ba.x = b.y / 2 + b.size; ba.y = -1; return HalfHorz(ba); }
    }
    static void BlockFill(Plane pl, int size, int ax, int ay, Func<BXY, int> pick) {
        var b = new BXY { size = size, pl = pl, w = pl.w, h = pl.h, ax = ax, ay = ay };
        for (int y = 0; y < size; y++) { b.y = y; for (int x = 0; x < size; x++) { b.x = x; int v = pick(b); pl.d[(ay + y) * pl.w + ax + x] = (byte)v; } }
    }
    static int Adjust(int x, int size) => size == 16 ? (x + 1) >> 1 : x;

    void PredictIntra(int ax, int ay, int pmode, int size, int plane) {
        var pl = pics[cur].p[plane]; int ls = pl.w;
        switch (pmode) {
            case 0: BlockFill(pl, size, ax, ay, PickAbove); break;
            case 1: BlockFill(pl, size, ax, ay, PickLeft); break;
            case 2: {
                int topo = Math.Max(ay - 1, 0) * ls + ax;
                int lefto = ay * ls + Math.Max(ax - 1, 0);
                int bottommost = pl.d[(ay + size - 1) * ls + Math.Max(ax - 1, 0)];
                int rightmost = pl.d[Math.Max(ay - 1, 0) * ls + ax + size - 1];
                int se = CSE(); se = Math.Clamp(se, -(1 << 16), 1 << 16);
                int avg = (bottommost + rightmost + 1) / 2 + 2 * se;
                int r6 = Adjust(avg - bottommost, size), r9 = Adjust(avg - rightmost, size);
                int shift = Adjust(size, size) == 8 ? 3 : 2;
                var arr1 = new int[16]; var arr2 = new int[16];
                for (int x = 0; x < size; x++) arr1[x] = Adjust(((bottommost - pl.d[topo + x]) * (1 << shift)) + r6 * (x + 1), size);
                for (int y = 0; y < size; y++) arr2[y] = Adjust(((rightmost - pl.d[lefto + y * ls]) * (1 << shift)) + r9 * (y + 1), size);
                var top = new int[size]; for (int x = 0; x < size; x++) top[x] = pl.d[topo + x];
                var left = new int[size]; for (int y = 0; y < size; y++) left[y] = pl.d[lefto + y * ls];
                for (int y = 0; y < size; y++)
                    for (int x = 0; x < size; x++)
                        pl.d[(ay + y) * ls + ax + x] = (byte)((((top[x] + left[y] + ((arr1[x] * (y + 1) + arr2[y] * (x + 1)) >> 2 * shift)) + 1) / 2) & 0xFF);
                break;
            }
            case 3: {
                int fill;
                if (ax == 0 && ay == 0) fill = 0x80;
                else if (ax >= 1 && ay >= 1) {
                    int l = 0, t = 0; for (int i = 0; i < size; i++) { l += pl.d[(ay + i) * ls + ax - 1]; t += pl.d[(ay - 1) * ls + ax + i]; }
                    fill = ((l + t) * 2 / (2 * size) + 1) / 2;
                } else if (ax >= 1) { int l = 0; for (int i = 0; i < size; i++) l += pl.d[(ay + i) * ls + ax - 1]; fill = (l * 2 / size + 1) / 2; }
                else { int t = 0; for (int i = 0; i < size; i++) t += pl.d[(ay - 1) * ls + ax + i]; fill = (t * 2 / size + 1) / 2; }
                for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) pl.d[(ay + y) * ls + ax + x] = (byte)fill;
                break;
            }
            case 4: BlockFill(pl, size, ax, ay, Pick4); break;
            case 5: BlockFill(pl, size, ax, ay, Pick5); break;
            case 6: BlockFill(pl, size, ax, ay, Pick6); break;
            case 7: BlockFill(pl, size, ax, ay, Pick7); break;
            case 8: BlockFill(pl, size, ax, ay, Pick8); break;
        }
    }

    int GetPrediction(int x, int y, int size) {
        int index = (y & 0xC) | (x / 4 % 4);
        int val = Math.Min(pre[index], index % 4 == 0 ? 9 : pre[index + 3]);
        if (val == 9) val = 3;
        if (CBit() == 0) { int v = CBits(3); val = v + (v >= val ? 1 : 0); }
        pre[index + 4] = val;
        if (size == 8) pre[index + 5] = pre[index + 8] = pre[index + 9] = val;
        return val;
    }

    // intra 8x8 block. origHas: original has_coeffs flag. Returns my has_coeffs flag; in transcode mode output goes to blockW
    int ProcessBlock(BitW mbw, int x, int y, int pmode, int origHas, int plane) {
        if (!transcode) {
            if (origHas == 0) { if (pmode < 0) pmode = GetPrediction(x, y, 8); PredictIntra(x, y, pmode, 8, plane); return 0; }
            int tmp = R.UE();
            if (tmp > 16) throw new Exception("tmp");
            if (tmp == 0) { if (pmode < 0) pmode = GetPrediction(x, y, 8); PredictIntra(x, y, pmode, 8, plane); SkipOrApplyCoeffs(x, y, 8, plane, true); }
            else {
                int fl = T.blk4[tmp - 1];
                for (int by = y; by < y + 8; by += 4) for (int bx = x; bx < x + 8; bx += 4) {
                    int nm = pmode; if (nm < 0) nm = GetPrediction(bx, by, 4);
                    PredictIntra(bx, by, nm, 4, plane);
                    if ((fl & 1) != 0) SkipOrApplyCoeffs(bx, by, 4, plane, true);
                    fl >>= 1;
                }
            }
            return 1;
        }
        // transcode
        var saveW = Wt;
        int otmp = origHas != 0 ? R.UE() : 0;
        if (origHas == 0 || otmp == 0) {
            var bw = new BitW(); Wt = bw;
            if (pmode < 0) pmode = GetPrediction(x, y, 8);
            PredictIntra(x, y, pmode, 8, plane);
            int[] olv = origHas != 0 ? SkipOrApplyCoeffs(x, y, 8, plane, false) : null;
            var cw = new BitW();
            bool has = EncodeBlock(cw, x, y, 8, plane, olv);
            Wt = saveW;
            if (has) { mbw.UE(0); mbw.Append(bw); mbw.Append(cw); return 1; }
            mbw.Append(bw); return 0;
        } else {
            int ofl = T.blk4[otmp - 1]; int myfl = 0, bit = 0;
            var bw = new BitW();
            for (int by = y; by < y + 8; by += 4) for (int bx = x; bx < x + 8; bx += 4) {
                Wt = bw;
                int nm = pmode; if (nm < 0) nm = GetPrediction(bx, by, 4);
                PredictIntra(bx, by, nm, 4, plane);
                int[] olv = (ofl & 1) != 0 ? SkipOrApplyCoeffs(bx, by, 4, plane, false) : null;
                ofl >>= 1;
                Wt = saveW;
                if (EncodeBlock(bw, bx, by, 4, plane, olv)) myfl |= 1 << bit;
                bit++;
            }
            int tmp = Array.IndexOf(T.blk4, myfl) + 1;
            mbw.UE(tmp); mbw.Append(bw); return 1;
        }
    }

    void DecodeMacroblock(int x, int y, int predict) {
        int idx = R.UE();
        if (idx < 0 || idx >= 64) throw new Exception("mb idx");
        int oflags = T.blk8[idx];
        var saveW = Wt; BitW mbw = transcode ? new BitW() : null;
        int myflags = 0;
        if (transcode) Wt = mbw;
        if (predict != 0) {
            int[,] pos = { { 0, 0 }, { 8, 0 }, { 0, 8 }, { 8, 8 } };
            for (int i = 0; i < 4; i++) { if (ProcessBlock(mbw, x + pos[i, 0], y + pos[i, 1], -1, oflags & 1, 0) != 0) myflags |= 1 << i; oflags >>= 1; Wt = mbw; }
        } else {
            int pmode = CBits(3);
            if (pmode == 2) { PredictIntra(x, y, pmode, 16, 0); pmode = 9; }
            int[,] pos = { { 0, 0 }, { 8, 0 }, { 0, 8 }, { 8, 8 } };
            for (int i = 0; i < 4; i++) { if (ProcessBlock(mbw, x + pos[i, 0], y + pos[i, 1], pmode, oflags & 1, 0) != 0) myflags |= 1 << i; oflags >>= 1; Wt = mbw; }
        }
        int puv = CBits(3);
        int pa = 1 + (moflex == 0 ? 1 : 0), pb = 2 - (moflex == 0 ? 1 : 0);
        if (puv == 2) { PredictIntra(x >> 1, y >> 1, puv, 8, pa); PredictIntra(x >> 1, y >> 1, puv, 8, pb); puv = 9; }
        if (ProcessBlock(mbw, x >> 1, y >> 1, puv, oflags & 1, pa) != 0) myflags |= 1 << 4; oflags >>= 1; Wt = mbw;
        if (ProcessBlock(mbw, x >> 1, y >> 1, puv, oflags & 1, pb) != 0) myflags |= 1 << 5;
        if (transcode) { Wt = saveW; Wt.UE(Array.IndexOf(T.blk8, myflags)); Wt.Append(mbw); }
    }

    static int GetIndex(int x) => x == 16 ? 0 : x == 8 ? 1 : x == 4 ? 2 : x == 2 ? 3 : 0;
    static int Mid(int a, int b, int c) => Math.Max(Math.Min(a, b), Math.Min(Math.Max(a, b), c));

    void PredictMotion(int width, int height, int index, int offm, int offx, int offy) {
        int fh = H, fw = W;
        if (index <= 5) {
            int sidx = -Math.Max(1, index) + cur; if (sidx < 0) sidx += 6;
            int mvx = mx[0], mvy = my[0];
            if (index > 0) { mvx += CSE(); mvy += CSE(); }
            mx[offm] = mvx; my[offm] = mvy;
            for (int i = 0; i < 3; i++) {
                if (i == 1) { offx >>= 1; offy >>= 1; mvx >>= 1; mvy >>= 1; width >>= 1; height >>= 1; fw >>= 1; fh >>= 1; }
                int method = (mvx & 1) | ((mvy & 1) << 1);
                var sp = pics[sidx].p[i]; var dp = pics[cur].p[i]; int sl = sp.w, dl = dp.w;
                if (offx + (mvx >> 1) < 0 || offy + (mvy >> 1) < 0 || offx + width + ((mvx + 1) >> 1) > fw || offy + height + ((mvy + 1) >> 1) > fh) throw new Exception("mv oob");
                int so = offx + (mvx >> 1) + (offy + (mvy >> 1)) * sl; int dof = offx + offy * dl;
                for (int y = 0; y < height; y++) {
                    for (int x = 0; x < width; x++) {
                        int v;
                        switch (method) {
                            case 0: v = sp.d[so + x]; break;
                            case 1: v = (sp.d[so + x] >> 1) + (sp.d[so + x + 1] >> 1); break;
                            case 2: v = (sp.d[so + x] >> 1) + (sp.d[so + x + sl] >> 1); break;
                            default: v = (((sp.d[so + x] >> 1) + (sp.d[so + x + 1] >> 1)) >> 1) + (((sp.d[so + x + sl] >> 1) + (sp.d[so + x + 1 + sl] >> 1)) >> 1); break;
                        }
                        dp.d[dof + x] = (byte)v;
                    }
                    so += sl; dof += dl;
                }
            }
        } else {
            int adjx = index == 8 ? 0 : width / 2, adjy = index == 8 ? height / 2 : 0;
            width -= adjx; height -= adjy;
            int tidx = GetIndex(height) * 4 + GetIndex(width);
            for (int i = 0; i < 2; i++) { int idx2 = CMV(tidx); PredictMotion(width, height, idx2, offm, offx + i * adjx, offy + i * adjy); }
        }
    }

    // P-frame residual block (8x8 region). returns my flag
    bool PCoeffs(BitW w, int bx, int by, int plane, bool orig) {
        if (!transcode) {
            int idx = R.UE();
            if (idx == 0) SkipOrApplyCoeffs(bx, by, 8, plane, true);
            else { int fl = T.pblk4[idx]; for (int y = by; y < by + 8; y += 4) for (int x = bx; x < bx + 8; x += 4) { if ((fl & 1) != 0) SkipOrApplyCoeffs(x, y, 4, plane, true); fl >>= 1; } }
            return true;
        }
        int oidx = -1; var subs = new int[4][];
        if (orig) {
            oidx = R.UE();
            if (oidx == 0) subs[0] = SkipOrApplyCoeffs(bx, by, 8, plane, false);
            else { int fl = T.pblk4[oidx]; int k = 0; for (int y = by; y < by + 8; y += 4) for (int x = bx; x < bx + 8; x += 4) { if ((fl & 1) != 0) subs[k] = SkipOrApplyCoeffs(x, y, 4, plane, false); fl >>= 1; k++; } }
        }
        if (!Changed(bx, by, 8, plane)) {
            if (!orig) {
                double e0 = SimErr(null, bx, by, 8, plane, out int m0);
                if (e0 <= reuseThr && m0 <= reuseMax) return false;
            } else if (oidx == 0) {
                var c = Rescale(subs[0], 8); double e = SimErr(c, bx, by, 8, plane, out int mm);
                if (e <= reuseThr && mm <= reuseMax) {
                    if (!AnyNZ(c)) return false;
                    ApplyLevels(c, 8, plane, bx, by, pics[cur]); w.UE(0); WriteLevels(w, c, 8); return true;
                }
            } else {
                var save = new byte[64]; var pl = pics[cur].p[plane];
                for (int y = 0; y < 8; y++) for (int x = 0; x < 8; x++) save[y * 8 + x] = pl.d[(by + y) * pl.w + bx + x];
                int k = 0; int myfl = 0; var cs = new int[4][];
                for (int y = by; y < by + 8; y += 4) for (int x = bx; x < bx + 8; x += 4) { cs[k] = Rescale(subs[k], 4); if (AnyNZ(cs[k])) { ApplyLevels(cs[k], 4, plane, x, y, pics[cur]); myfl |= 1 << k; } k++; }
                var tg = target.p[plane]; double e = 0; int mm = 0;
                for (int y = 0; y < 8; y++) for (int x = 0; x < 8; x++) { int d = Math.Abs(pl.d[(by + y) * pl.w + bx + x] - tg.d[(by + y) * pl.w + bx + x]); e += d; if (d > mm) mm = d; }
                e /= 64;
                if (e <= reuseThr && mm <= reuseMax) {
                    if (myfl == 0) return false;
                    w.UE(Array.IndexOf(T.pblk4, myfl)); for (int j = 0; j < 4; j++) if (((myfl >> j) & 1) != 0) WriteLevels(w, cs[j], 4);
                    return true;
                }
                for (int y = 0; y < 8; y++) for (int x = 0; x < 8; x++) pl.d[(by + y) * pl.w + bx + x] = save[y * 8 + x];
            }
        }
        var lv = Quantize(bx, by, 8, plane);
        if (!AnyNZ(lv)) return false;
        ApplyLevels(lv, 8, plane, bx, by, pics[cur]);
        w.UE(0); WriteLevels(w, lv, 8); return true;
    }


    // ---------- motion re-encoding (transcode) ----------
    class Leaf { public int idx, refi, mvx, mvy, w, h, ox, oy; }
    class Node { public int tidx, sym; public Node a, b; public Leaf leaf; }
    Node ParseNode(int tidx, int width, int height, int idx, int offx, int offy, int px, int py, List<Leaf> leaves) {
        var n = new Node { tidx = tidx, sym = idx };
        if (idx <= 5) {
            var l = new Leaf { idx = idx, refi = Math.Max(1, idx), mvx = px, mvy = py, w = width, h = height, ox = offx, oy = offy };
            if (idx > 0) { l.mvx += R.SE(); l.mvy += R.SE(); }
            n.leaf = l; leaves.Add(l); return n;
        }
        int adjx = idx == 8 ? 0 : width / 2, adjy = idx == 8 ? height / 2 : 0;
        int w2 = width - adjx, h2 = height - adjy;
        int nt = GetIndex(h2) * 4 + GetIndex(w2);
        for (int i = 0; i < 2; i++) {
            int sym = mv[moflex, nt].Read(R);
            var c = ParseNode(nt, w2, h2, sym, offx + i * adjx, offy + i * adjy, px, py, leaves);
            if (i == 0) n.a = c; else n.b = c;
        }
        return n;
    }
    void WriteNode(Node n, int px, int py) {
        if (n.leaf != null) {
            var l = n.leaf; int sym = l.idx;
            if (sym == 0 && (l.mvx != px || l.mvy != py)) sym = 1;
            mv[moflex, n.tidx].Write(Wt, sym);
            if (sym > 0) { Wt.SE(l.mvx - px); Wt.SE(l.mvy - py); }
            return;
        }
        mv[moflex, n.tidx].Write(Wt, n.sym);
        WriteNode(n.a, px, py); WriteNode(n.b, px, py);
    }
    void ApplyLeaf(Leaf l) {
        int sidx = cur - l.refi; if (sidx < 0) sidx += 6;
        int offx = l.ox, offy = l.oy, mvx = l.mvx, mvy = l.mvy, width = l.w, height = l.h;
        for (int i = 0; i < 3; i++) {
            if (i == 1) { offx >>= 1; offy >>= 1; mvx >>= 1; mvy >>= 1; width >>= 1; height >>= 1; }
            int method = (mvx & 1) | ((mvy & 1) << 1);
            var sp = pics[sidx].p[i]; var dp = pics[cur].p[i]; int sl = sp.w, dl = dp.w;
            int so = offx + (mvx >> 1) + (offy + (mvy >> 1)) * sl; int dof = offx + offy * dl;
            for (int y = 0; y < height; y++) {
                for (int x = 0; x < width; x++) {
                    int v;
                    switch (method) {
                        case 0: v = sp.d[so + x]; break;
                        case 1: v = (sp.d[so + x] >> 1) + (sp.d[so + x + 1] >> 1); break;
                        case 2: v = (sp.d[so + x] >> 1) + (sp.d[so + x + sl] >> 1); break;
                        default: v = (((sp.d[so + x] >> 1) + (sp.d[so + x + 1] >> 1)) >> 1) + (((sp.d[so + x + sl] >> 1) + (sp.d[so + x + 1 + sl] >> 1)) >> 1); break;
                    }
                    dp.d[dof + x] = (byte)v;
                }
                so += sl; dof += dl;
            }
        }
    }
    long[] QuadSAD(int x, int y) {
        var r = new long[4];
        var a = pics[cur].p[0]; var t = target.p[0];
        for (int k = 0; k < 4; k++) {
            int qx = x + (k & 1) * 8, qy = y + (k >> 1) * 8; long s = 0;
            for (int j = 0; j < 8; j++) for (int i = 0; i < 8; i++) { int o = (qy + j) * a.w + qx + i; s += Math.Abs(a.d[o] - t.d[o]); }
            for (int pl = 1; pl < 3; pl++) { var b = pics[cur].p[pl]; var u = target.p[pl]; for (int j = 0; j < 4; j++) for (int i = 0; i < 4; i++) { int o = (qy / 2 + j) * b.w + qx / 2 + i; s += 2 * Math.Abs(b.d[o] - u.d[o]); } }
            r[k] = s;
        }
        return r;
    }
    long MbSAD(int x, int y) {
        long s = 0;
        var a = pics[cur].p[0]; var t = target.p[0];
        for (int j = 0; j < 16; j++) for (int i = 0; i < 16; i++) { int k = (y + j) * a.w + x + i; s += Math.Abs(a.d[k] - t.d[k]); }
        for (int pl = 1; pl < 3; pl++) { var b = pics[cur].p[pl]; var u = target.p[pl]; for (int j = 0; j < 8; j++) for (int i = 0; i < 8; i++) { int k = (y / 2 + j) * b.w + x / 2 + i; s += Math.Abs(b.d[k] - u.d[k]); } }
        return s;
    }
    public static int nZero, nTextMb;
    void TranscodePMotion(int x, int y) {
        int c = x / 16;
        int opx = Mid(omx[c + 1], omx[c + 2], omx[c + 3]), opy = Mid(omy[c + 1], omy[c + 2], omy[c + 3]);
        int mpx = Mid(mx[c + 1], mx[c + 2], mx[c + 3]), mpy = Mid(my[c + 1], my[c + 2], my[c + 3]);
        omx[c + 2] = omy[c + 2] = 0; mx[c + 2] = my[c + 2] = 0;
        int idx = mv[moflex, 0].Read(R);
        if (idx == 6 || idx == 7) { mv[moflex, 0].Write(Wt, idx); DecodeMacroblock(x, y, idx == 7 ? 1 : 0); return; }
        var leaves = new List<Leaf>();
        var root = ParseNode(0, 16, 16, idx, x, y, opx, opy, leaves);
        omx[c + 2] = leaves[leaves.Count - 1].mvx; omy[c + 2] = leaves[leaves.Count - 1].mvy;
        var use = root; var useLeaves = leaves;
        bool chg = Changed(x, y, 16, 0) || Changed(x / 2, y / 2, 8, 1) || Changed(x / 2, y / 2, 8, 2);
        if (chg && root.leaf != null) {
            nTextMb++;
            var ol = root.leaf;
            ApplyLeaf(ol); var sadO = QuadSAD(x, y);
            var z = new Leaf { idx = 1, refi = 1, mvx = 0, mvy = 0, w = 16, h = 16, ox = x, oy = y };
            ApplyLeaf(z); var sadZ = QuadSAD(x, y);
            var ch = new bool[4]; int nz = 0;
            for (int k = 0; k < 4; k++) { ch[k] = sadZ[k] < sadO[k] * zeroBias || zeroBias >= 100; if (ch[k]) nz++; }
            if (nz == 4) { use = new Node { tidx = 0, sym = 1, leaf = z }; useLeaves = new List<Leaf> { z }; nZero++; }
            else if (nz > 0) {
                nZero++;
                useLeaves = new List<Leaf>();
                Leaf Mk(bool zero, int w, int h, int ox, int oy) => zero ? new Leaf { idx = 1, refi = 1, mvx = 0, mvy = 0, w = w, h = h, ox = ox, oy = oy }
                                                                            : new Leaf { idx = ol.idx, refi = ol.refi, mvx = ol.mvx, mvy = ol.mvy, w = w, h = h, ox = ox, oy = oy };
                var rootN = new Node { tidx = 0, sym = 8 };
                for (int hf = 0; hf < 2; hf++) {
                    bool a = ch[hf * 2], b = ch[hf * 2 + 1];
                    Node hn;
                    if (a == b) { var lf = Mk(a, 16, 8, x, y + hf * 8); hn = new Node { tidx = 4, sym = lf.idx, leaf = lf }; useLeaves.Add(lf); }
                    else {
                        hn = new Node { tidx = 4, sym = 9 };
                        var l0 = Mk(a, 8, 8, x, y + hf * 8); var l1 = Mk(b, 8, 8, x + 8, y + hf * 8);
                        hn.a = new Node { tidx = 5, sym = l0.idx, leaf = l0 }; hn.b = new Node { tidx = 5, sym = l1.idx, leaf = l1 };
                        useLeaves.Add(l0); useLeaves.Add(l1);
                    }
                    if (hf == 0) rootN.a = hn; else rootN.b = hn;
                }
                use = rootN;
            }
        }
        foreach (var l in useLeaves) ApplyLeaf(l);
        WriteNode(use, mpx, mpy);
        mx[c + 2] = useLeaves[useLeaves.Count - 1].mvx; my[c + 2] = useLeaves[useLeaves.Count - 1].mvy;
        int idx2 = R.UE(); if (idx2 >= 64) throw new Exception("pidx");
        int fl = T.pblk8[idx2]; int myf = 0; var bw = new BitW(); int bit = 0;
        for (int sy = y; sy < y + 16; sy += 8) for (int sx = x; sx < x + 16; sx += 8) { if (PCoeffs(bw, sx, sy, 0, (fl & 1) != 0)) myf |= 1 << bit; fl >>= 1; bit++; }
        int pa = 1 + (moflex == 0 ? 1 : 0), pb = 2 - (moflex == 0 ? 1 : 0);
        if (PCoeffs(bw, x >> 1, y >> 1, pa, (fl & 1) != 0)) myf |= 1 << 4; fl >>= 1;
        if (PCoeffs(bw, x >> 1, y >> 1, pb, (fl & 1) != 0)) myf |= 1 << 5;
        Wt.UE(Array.IndexOf(T.pblk8, myf)); Wt.Append(bw);
    }
    public void Frame(byte[] pkt, BitW outw, Pic tgt, int qOverride = -1, Pic orig = null, int oq = -1) {
        origPic = orig; origQ = oq;
        R = new BitR(pkt); Wt = outw; target = tgt; tmode = outw != null;
        int key = R.Bit();
        if (key == 1) {
            moflex = R.Bit(); dctIdx = R.Bit(); int q = R.Bits(6);
            if (qOverride >= 0) q = qOverride;
            if (Wt != null) { Wt.Bit(1); Wt.Bit(moflex); Wt.Bit(dctIdx); Wt.Bits(q, 6); }
            SetupQ(q);
            for (int y = 0; y < H; y += 16) for (int x = 0; x < W; x += 16) { int p = CBit(); DecodeMacroblock(x, y, p); }
        } else {
            Array.Clear(mx); Array.Clear(my);
            dctIdx = 0;
            int dq = R.SE(); int q = quant + dq;
            if (qOverride >= 0) q = qOverride;
            if (Wt != null) { Wt.Bit(0); Wt.SE(q - quant); }
            SetupQ(q);
            if (transcode) {
                Array.Clear(omx); Array.Clear(omy);
                for (int y = 0; y < H; y += 16) for (int x = 0; x < W; x += 16) TranscodePMotion(x, y);
            } else
            for (int y = 0; y < H; y += 16) for (int x = 0; x < W; x += 16) {
                mx[0] = Mid(mx[x / 16 + 1], mx[x / 16 + 2], mx[x / 16 + 3]);
                my[0] = Mid(my[x / 16 + 1], my[x / 16 + 2], my[x / 16 + 3]);
                mx[x / 16 + 2] = 0; my[x / 16 + 2] = 0;
                int idx = CMV(0);
                if (idx == 6 || idx == 7) DecodeMacroblock(x, y, idx == 7 ? 1 : 0);
                else {
                    PredictMotion(16, 16, idx, x / 16 + 2, x, y);
                    int idx2 = R.UE(); if (idx2 >= 64) throw new Exception("pidx");
                    int fl = T.pblk8[idx2]; int my_ = 0; var bw = transcode ? new BitW() : null;
                    int bit = 0;
                    for (int sy = y; sy < y + 16; sy += 8) for (int sx = x; sx < x + 16; sx += 8) {
                        if (transcode) { if (PCoeffs(bw, sx, sy, 0, (fl & 1) != 0)) my_ |= 1 << bit; }
                        else if ((fl & 1) != 0) PCoeffs(null, sx, sy, 0, true);
                        fl >>= 1; bit++;
                    }
                    int pa = 1 + (moflex == 0 ? 1 : 0), pb = 2 - (moflex == 0 ? 1 : 0);
                    if (transcode) { if (PCoeffs(bw, x >> 1, y >> 1, pa, (fl & 1) != 0)) my_ |= 1 << 4; }
                    else if ((fl & 1) != 0) PCoeffs(null, x >> 1, y >> 1, pa, true);
                    fl >>= 1;
                    if (transcode) { if (PCoeffs(bw, x >> 1, y >> 1, pb, (fl & 1) != 0)) my_ |= 1 << 5; }
                    else if ((fl & 1) != 0) PCoeffs(null, x >> 1, y >> 1, pb, true);
                    if (transcode) { Wt.UE(Array.IndexOf(T.pblk8, my_)); Wt.Append(bw); }
                }
            }
        }
        cur = (cur + 1) % 6;
        Wt = null; tmode = false;
    }
    public Pic Last => pics[(cur + 5) % 6];
    public bool IsKey(byte[] pkt) => (new BitR(pkt)).Bit() == 1;
}

static class Program {
    // packets file: [u32 n] then n * [u32 len][bytes]
    static List<byte[]> ReadPkts(string f) {
        var br = new BinaryReader(File.OpenRead(f)); int n = br.ReadInt32(); var l = new List<byte[]>();
        for (int i = 0; i < n; i++) { int len = br.ReadInt32(); l.Add(br.ReadBytes(len)); }
        return l;
    }
    static void WritePic(string f, Pic p) {
        using var fs = File.Create(f); foreach (var pl in p.p) fs.Write(pl.d);
    }
    static Pic ReadPic(string f, int w, int h) {
        var p = new Pic(w, h); var b = File.ReadAllBytes(f); int o = 0;
        foreach (var pl in p.p) { Array.Copy(b, o, pl.d, 0, pl.d.Length); o += pl.d.Length; }
        return p;
    }
    static int Main(string[] a) {
        int W = int.Parse(a[2]), H = int.Parse(a[3]);
        var pk = ReadPkts(a[1]);
        if (a[0] == "decode") {
            // decode <pkts> W H outdir from to   (dumps frames in [from,to])
            int from = int.Parse(a[5]), to = int.Parse(a[6]);
            Directory.CreateDirectory(a[4]);
            var m = new Mobi(W, H);
            for (int i = 0; i <= to && i < pk.Count; i++) {
                m.Frame(pk[i], null, null);
                if (i >= from) WritePic(Path.Combine(a[4], $"{i:D5}.yuv"), m.Last);
            }
            return 0;
        }
        if (a[0] == "keys") {
            var m = new Mobi(W, H);
            Console.WriteLine(string.Join(",", Enumerable.Range(0, pk.Count).Where(i => m.IsKey(pk[i]))));
            return 0;
        }
        if (a[0] == "transcode") {
            // transcode <pkts> W H targetdir from to outpkts
            string td = a[4]; int from = int.Parse(a[5]), to = int.Parse(a[6]);
            var m = new Mobi(W, H);
            for (int i = 0; i < from; i++) m.Frame(pk[i], null, null);
            var refdec = m.CloneState();
            var outp = new List<(int, byte[])>();
            for (int i = from; i <= to; i++) {
                var tf = Path.Combine(td, $"{i:D5}.yuv");
                refdec.Frame(pk[i], null, null);
                Pic tgt;
                if (File.Exists(tf)) tgt = ReadPic(tf, W, H);
                else tgt = refdec.Last.Clone();
                byte[] res = null; int tries = 0; Mobi ok = null; int usedQ = -1; string used = "";
                int oq = refdec.lastQuant;
                var plan = new List<(int dq, double dz, double thr, int mx, int hf, double zb, int tp)> {
                    (0, 0.15, 1.5, 14, 64, 0.9, 999), (0, 0.30, 2.5, 20, 64, 1.0, 999), (0, 0.45, 3.0, 24, 48, 1.2, 999), (0, 0.60, 3.5, 28, 40, 1.5, 999),
                    (0, 0.70, 4.0, 32, 36, 2.0, 40), (0, 0.75, 4.5, 36, 32, 3.0, 28), (0, 0.80, 5.0, 40, 28, 3.0, 20), (0, 0.85, 5.0, 40, 24, 5.0, 14) };
                for (int dq = 1; dq <= 12; dq++) plan.Add((dq, 0.6, 4.0, 32, 40, 2.0, 40));
                foreach (var st in plan) {
                    int qo = oq + st.dq; if (qo > 161) break;
                    var t = m.CloneState(); t.deadzone = st.dz; t.reuseThr = st.thr; t.reuseMax = st.mx; t.hfCap = st.hf; t.zeroBias = st.zb; t.trimPos = st.tp;
                    var w = new BitW();
                    t.Frame(pk[i], w, tgt, qo, refdec.Last, oq);
                    int nbytes = (w.Count + 7) / 8;
                    if (Environment.GetEnvironmentVariable("MOBI_PROF") != null) { Console.WriteLine($"  q={qo} dz={st.dz} bits={w.Count} budget={pk[i].Length * 8} reuse={Mobi.nReuse} quant={Mobi.nQuant} chg={Mobi.nChanged} textmb={Mobi.nTextMb} zero={Mobi.nZero}"); Mobi.nReuse = Mobi.nQuant = Mobi.nChanged = Mobi.nTextMb = Mobi.nZero = 0; }
                    bool nob = Environment.GetEnvironmentVariable("MOBI_NOBUDGET") != null;
                    if (nob) { res = w.ToBytes(0); ok = t; usedQ = qo; used = $"free bytes={res.Length} orig={pk[i].Length}"; break; }
                    if (nbytes <= pk[i].Length) { res = w.ToBytes(pk[i].Length); ok = t; usedQ = qo; used = $"dz={st.dz} thr={st.thr} zb={st.zb} tp={st.tp}"; break; }
                    tries++;
                }
                if (ok == null) {
                    // passthrough: original bitstream decoded on our references
                    var t = m.CloneState(); t.Frame(pk[i], null, null); ok = t; res = (byte[])pk[i].Clone(); usedQ = oq; used = "PASSTHROUGH";
                }
                {
                    var v = m.CloneState(); v.Frame(res, null, null);
                    var A = v.Last; var Bp = ok.Last; int bad = -1;
                    for (int pl = 0; pl < 3 && bad < 0; pl++) for (int k = 0; k < A.p[pl].d.Length; k++) if (A.p[pl].d[k] != Bp.p[pl].d[k]) { bad = pl * 1000000 + k; break; }
                    if (bad >= 0) Console.WriteLine($"VERIFY MISMATCH frame {i} plane {bad / 1000000} pos {bad % 1000000} (x={bad % 1000000 % (bad / 1000000 == 0 ? W : W / 2)}, y={bad % 1000000 / (bad / 1000000 == 0 ? W : W / 2)})");
                }
                m = ok;
                if (Environment.GetEnvironmentVariable("MOBI_NOBUDGET") == null && res.Length != pk[i].Length) { var r2 = new byte[pk[i].Length]; Array.Copy(res, r2, pk[i].Length); res = r2; }
                outp.Add((i, res));
                Console.WriteLine($"frame {i} oq={oq} q={usedQ} tries={tries} {used}");
            }
            // verify by decoding output with fresh decoder from 0
            using (var bw = new BinaryWriter(File.Create(a[7]))) {
                bw.Write(outp.Count);
                foreach (var (i, b) in outp) { bw.Write(i); bw.Write(b.Length); bw.Write(b); }
            }
            return 0;
        }
        return 1;
    }
}

#!/usr/bin/env python3
"""Render the recorded-instrument loops used by exercises/frequency-hunt.html.

Each loop is arranged here from single recorded notes, mixed with numpy, and written as an MP3
with half a second of wrap-around audio on each side.  The page loops between PRE and PRE+length,
so the loop stays seamless even if a browser doesn't trim the MP3 encoder delay.

Sources (see exercises/audio/CREDITS.md):
  git clone --depth 1 https://github.com/nbrosowsky/tonejs-instruments   -> --inst <repo>/samples
  git clone --depth 1 https://github.com/Tonejs/audio                    -> --drums <repo>/drum-samples/acoustic-kit

usage: python3 tools/render-loops.py --inst DIR --drums DIR [--out exercises/audio]
Needs numpy and ffmpeg.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np

SR = 44100
PRE = 0.5
ap = argparse.ArgumentParser()
ap.add_argument('--inst', required=True)
ap.add_argument('--drums', required=True)
ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'exercises', 'audio'))
ap.add_argument('--only')
args = ap.parse_args()

def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)

NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
def midi_of(name):
    m = re.fullmatch(r'([A-G])(s?)(-?\d)', name)
    return None if not m else 12 * (int(m[3]) + 1) + NOTE[m[1]] + (1 if m[2] else 0)

def m(s):
    """'A3' / 'C#4' / 'Bb2' -> midi"""
    r = re.fullmatch(r'([A-G])([#b]?)(-?\d)', s)
    return 12 * (int(r[3]) + 1) + NOTE[r[1]] + {'#': 1, 'b': -1, '': 0}[r[2]]

class Inst:
    def __init__(self, name):
        d = os.path.join(args.inst, name)
        self.notes = {}
        for f in os.listdir(d):
            base, ext = os.path.splitext(f)
            if ext == '.wav' and midi_of(base) is not None:
                self.notes[midi_of(base)] = os.path.join(d, f)
        self.cache = {}
        if not self.notes:
            sys.exit(f'no samples in {d}')

    def get(self, midi):
        src = min(self.notes, key=lambda k: (abs(k - midi), k < midi))
        key = (src, midi)
        if key not in self.cache:
            a = load(self.notes[src])
            r = 2 ** ((midi - src) / 12)
            if r != 1:
                n = int(len(a) / r)
                x = np.arange(n) * r
                a = np.stack([np.interp(x, np.arange(len(a)), a[:, c]) for c in (0, 1)], 1)
            self.cache[key] = a
        return self.cache[key]

class Mix:
    def __init__(self, bpm, bars, beats=4, swing=0.0):
        self.beat = 60 / bpm
        self.len = bars * beats * self.beat
        self.buf = np.zeros((int((self.len + 12) * SR), 2))
        self.swing = swing

    def t(self, beat):
        if self.swing:
            whole, frac = divmod(beat, 1)
            if abs(frac - .5) < 1e-6:
                beat = whole + .5 + self.swing / 2
        return beat * self.beat

    def add(self, a, beat, vel=1.0, pan=0.0, dur=None, rel=.12, sec=None):
        if dur is not None:
            n = int((dur * self.beat + rel) * SR)
            a = a[:n].copy()
            fade = int(rel * SR)
            if len(a) > fade:
                a[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
        g = np.array([min(1, 1 - pan), min(1, 1 + pan)]) * vel
        i = int((sec if sec is not None else self.t(beat)) * SR)
        a = a[:len(self.buf) - i]
        self.buf[i:i + len(a)] += a * g

    def note(self, inst, note, beat, dur=None, vel=1.0, pan=0.0, rel=.12):
        self.add(inst.get(m(note) if isinstance(note, str) else note), beat, vel, pan, dur, rel)

    def render(self, rms_db=-21.0):
        L = int(round(self.len * SR))
        loop = self.buf[:L].copy()
        tail = self.buf[L:]
        k = 0
        while k < len(tail):          # wrap everything that rings past the end back onto the start
            seg = tail[k:k + L]
            loop[:len(seg)] += seg
            k += L
        rms = np.sqrt(np.mean(loop ** 2))
        loop *= 10 ** (rms_db / 20) / max(rms, 1e-9)
        peak = np.max(np.abs(loop))
        if peak > .97:                # never clip; the page sets the final level anyway
            loop *= .97 / peak
        p = int(PRE * SR)
        return np.concatenate([loop[-p:], loop, loop[:p]]), self.len

def chord(mx, inst, notes, beat, dur, vel=.5, strum=0.0, pan=0.0, spread=0.0, rel=.12):
    for i, n in enumerate(notes):
        p = pan + (i - (len(notes) - 1) / 2) * spread
        mx.note(inst, n, beat + i * strum, dur, vel, max(-1, min(1, p)), rel)

DR = {k: load(os.path.join(args.drums, k + '.mp3')) for k in ['kick', 'snare', 'hihat', 'tom1', 'tom2', 'tom3']}
def hit(mx, k, beat, vel=1.0, pan=0.0):
    mx.add(DR[k], beat, vel, pan)

I = {}
def inst(n):
    if n not in I:
        I[n] = Inst(n)
    return I[n]

# ---------------------------------------------------------------- arrangements
PROG = [['A2', ['A3', 'C4', 'E4', 'G4']], ['F2', ['F3', 'A3', 'C4', 'E4']],
        ['C3', ['G3', 'C4', 'E4', 'G4']], ['G2', ['G3', 'B3', 'D4', 'G4']]]

def piano():
    mx, p = Mix(80, 8), inst('piano')
    mel = [[(0, 'E5', 1.5), (1.5, 'D5', .5), (2, 'C5', 1), (3, 'B4', 1)],
           [(0, 'A4', 2), (2, 'C5', 1), (3, 'E5', 1)],
           [(0, 'G5', 1.5), (1.5, 'E5', .5), (2, 'D5', 1), (3, 'C5', 1)],
           [(0, 'B4', 3), (3, 'D5', 1)]] * 2
    for bar in range(8):
        b0, (root, ch) = bar * 4, PROG[bar % 4]
        mx.note(p, m(root) - 12, b0, 4, .55, -.3)
        mx.note(p, root, b0, 4, .45, -.2)
        for k, beat in enumerate([0, 1, 1.5, 2, 3, 3.5]):
            mx.note(p, ch[[0, 1, 2, 3, 2, 1][k]], b0 + beat, .9, .28, .1)
        for (b, n, d) in mel[bar]:
            mx.note(p, n, b0 + b, d, .62 if bar < 4 else .7, .25)
            if bar >= 4:
                mx.note(p, m(n) + 12, b0 + b, d, .25, .3)
    return mx

GTR = [['C3', 'E3', 'G3', 'C4', 'E4'], ['G2', 'B2', 'D3', 'G3', 'B3', 'G4'],
       ['A2', 'E3', 'A3', 'C4', 'E4'], ['F2', 'C3', 'F3', 'A3', 'C4', 'F4']]

def guitar():
    mx, g = Mix(92, 8), inst('guitar-acoustic')
    for bar in range(8):
        b0, ch = bar * 4, GTR[bar % 4]
        if bar < 4:   # fingerpicking
            order = [0, 2, 3, 4, 1, 3, 4, 3] if len(ch) == 5 else [0, 2, 3, 5, 1, 3, 4, 3]
            for k, idx in enumerate(order):
                mx.note(g, ch[idx], b0 + k * .5, 1.6, .55 if k % 2 == 0 else .42, -.25 + idx * .1)
        else:         # strumming: D DU UDU
            for beat, down, v in [(0, 1, .55), (1, 1, .4), (1.5, 0, .3), (2.5, 0, .3), (3, 1, .45), (3.5, 0, .3)]:
                notes = ch if down else list(reversed(ch[-4:]))
                chord(mx, g, notes, b0 + beat, .9, v, strum=.03, spread=.12)
    return mx

def drums():
    mx = Mix(96, 4)
    for bar in range(4):
        b0 = bar * 4
        for k in range(8):
            hit(mx, 'hihat', b0 + k * .5, .5 if k % 2 == 0 else .3, .35)
        for b in [0, 1.75, 2.5] if bar % 2 else [0, 2, 2.5]:
            hit(mx, 'kick', b0 + b, 1.0)
        for b in [1, 3]:
            hit(mx, 'snare', b0 + b, .85, -.05)
        hit(mx, 'snare', b0 + 3.75, .25, -.05)
    b0 = 12   # fill on the last bar's second half
    for b, k, pan in [(2, 'tom1', .3), (2.25, 'tom1', .3), (2.5, 'tom2', 0), (2.75, 'tom2', 0), (3, 'tom3', -.3), (3.25, 'tom3', -.3), (3.5, 'snare', 0), (3.75, 'snare', 0)]:
        hit(mx, k, b0 + b, .8, pan)
    return mx

BASS = [[(0, 'A1', .75), (.75, 'A1', .5), (1.5, 'E2', .5), (2, 'A2', .5), (2.5, 'G2', .5), (3, 'E2', .5), (3.5, 'C2', .5)],
        [(0, 'F1', .75), (.75, 'F1', .5), (1.5, 'C2', .5), (2, 'F2', .5), (2.5, 'E2', .5), (3, 'C2', .5), (3.5, 'A1', .5)],
        [(0, 'C2', .75), (.75, 'C2', .5), (1.5, 'G2', .5), (2, 'C3', .5), (2.5, 'B2', .5), (3, 'G2', .5), (3.5, 'E2', .5)],
        [(0, 'G1', .75), (.75, 'G1', .5), (1.5, 'D2', .5), (2, 'G2', 1), (3, 'B1', .5), (3.5, 'D2', .5)]]

def bass():
    mx, b = Mix(96, 8), inst('bass-electric')
    for bar in range(8):
        for (x, n, d) in BASS[bar % 4]:
            mx.note(b, n, bar * 4 + x, d * .95, .9 if x == 0 else .75, 0, rel=.05)
    return mx

def strings():
    mx, v, cb = Mix(66, 8), inst('violin'), inst('contrabass')
    roots = ['A1', 'F1', 'C2', 'G1']
    line = [[('E5', 0, 2), ('C5', 2, 2)], [('A4', 0, 2), ('C5', 2, 2)], [('G5', 0, 3), ('E5', 3, 1)], [('D5', 0, 4)],
            [('A5', 0, 2), ('G5', 2, 1), ('E5', 3, 1)], [('F5', 0, 2), ('E5', 2, 2)], [('E5', 0, 1), ('G5', 1, 1), ('C6', 2, 2)], [('B5', 0, 4)]]
    harm = [['C4', 'E4'], ['A3', 'C4'], ['G3', 'E4'], ['G3', 'D4']]
    for bar in range(8):
        b0 = bar * 4
        mx.note(cb, roots[bar % 4], b0, 3.8, .9, -.35, rel=.4)
        mx.note(cb, m(roots[bar % 4]) + 12, b0 + 2, 1.9, .5, -.35, rel=.3)
        for i, n in enumerate(harm[bar % 4]):
            mx.note(v, n, b0, 3.9, .32, -.1 + i * .2, rel=.5)
        for (n, x, d) in line[bar]:
            mx.note(v, n, b0 + x, d - .05, .6, .3, rel=.35)
    return mx

def flute_harp():
    mx, fl, hp = Mix(84, 8), inst('flute'), inst('harp')
    arps = [['A2', 'E3', 'A3', 'C4', 'E4', 'C4', 'A3', 'E3'], ['F2', 'C3', 'F3', 'A3', 'C4', 'A3', 'F3', 'C3'],
            ['C3', 'G3', 'C4', 'E4', 'G4', 'E4', 'C4', 'G3'], ['G2', 'D3', 'G3', 'B3', 'D4', 'B3', 'G3', 'D3']]
    mel = [[(0, 'E5', 1), (1, 'A5', 1), (2, 'G5', 1.5), (3.5, 'E5', .5)], [(0, 'F5', 2), (2, 'E5', 1), (3, 'C5', 1)],
           [(0, 'E5', 1), (1, 'G5', 1), (2, 'C6', 1.5), (3.5, 'B5', .5)], [(0, 'A5', 1), (1, 'G5', 1), (2, 'D5', 2)]]
    for bar in range(8):
        b0 = bar * 4
        for k, n in enumerate(arps[bar % 4]):
            mx.note(hp, n, b0 + k * .5, 3, .5, -.4 + k * .06)
        if bar >= 2:
            for (x, n, d) in mel[bar % 4]:
                mx.note(fl, n, b0 + x, d - .05, .55, .25, rel=.15)
    return mx

def jazz():
    mx = Mix(126, 8, swing=.33)
    sax, cb, p = inst('saxophone'), inst('contrabass'), inst('piano')
    walk = [['D2', 'F2', 'A2', 'C3'], ['G1', 'B1', 'D2', 'F2'], ['C2', 'E2', 'G2', 'B2'], ['A1', 'C#2', 'E2', 'G2']]
    comp = [['F3', 'A3', 'C4', 'E4'], ['F3', 'B3', 'D4', 'E4'], ['E3', 'G3', 'B3', 'D4'], ['G3', 'C#4', 'E4', 'Bb4']]
    mel = [[(0, 'A4', 1), (1, 'C5', .5), (1.5, 'D5', 1), (3, 'F5', 1)], [(0, 'E5', 1.5), (1.5, 'D5', .5), (2, 'B4', 2)],
           [(.5, 'G4', .5), (1, 'B4', .5), (1.5, 'D5', .5), (2, 'E5', 2)], [(0, 'C#5', 1), (1, 'E5', 1), (2, 'G5', 1.5), (3.5, 'F5', .5)],
           [(0, 'F5', .5), (.5, 'E5', .5), (1, 'D5', .5), (1.5, 'C5', .5), (2, 'A4', 2)], [(0, 'B4', 1), (1, 'D5', 1), (2, 'F5', 2)],
           [(0, 'E5', 3), (3, 'D5', 1)], [(0, 'C#5', 2), (2, 'A4', 2)]]
    for bar in range(8):
        b0 = bar * 4
        for k, n in enumerate(walk[bar % 4]):
            mx.note(cb, n, b0 + k, .95, .95, -.2, rel=.08)
        for x in ([1.5, 3] if bar % 2 else [0, 2.5]):
            chord(mx, p, comp[bar % 4], b0 + x, .7, .28, pan=.35, spread=.05)
        for x in range(4):      # brush-ish ride from the hi-hat, plus feathered kick
            hit(mx, 'hihat', b0 + x, .4, .4)
            if x % 2:
                hit(mx, 'hihat', b0 + x + .5, .25, .4)
                hit(mx, 'snare', b0 + x, .22, .1)
            hit(mx, 'kick', b0 + x, .25)
        for (x, n, d) in mel[bar]:
            mx.note(sax, n, b0 + x, d - .05, .55, -.05, rel=.1)
    return mx

def band():
    mx = Mix(100, 8)
    g, b, p, tr = inst('guitar-acoustic'), inst('bass-electric'), inst('piano'), inst('trumpet')
    for bar in range(8):
        b0 = bar * 4
        for k in range(8):
            hit(mx, 'hihat', b0 + k * .5, .45 if k % 2 == 0 else .28, .3)
        for x in [0, 1.5, 2.5]:
            hit(mx, 'kick', b0 + x, 1.0)
        for x in [1, 3]:
            hit(mx, 'snare', b0 + x, .9)
        for (x, n, d) in BASS[[2, 1, 0, 3][bar % 4]]:
            mx.note(b, n, b0 + x, d * .95, .85, 0, rel=.05)
        ch = GTR[[0, 3, 2, 1][bar % 4]]
        for x, v in [(0, .45), (1, .3), (1.5, .25), (2.5, .25), (3, .35), (3.5, .25)]:
            chord(mx, g, ch, b0 + x, .9, v, strum=.025, pan=-.45, spread=.05)
        pc = [['E4', 'G4', 'C5'], ['F4', 'A4', 'C5'], ['E4', 'A4', 'C5'], ['D4', 'G4', 'B4']][bar % 4]
        chord(mx, p, pc, b0, 3.8, .22, pan=.4, spread=.05)
    tmel = [[(0, 'G4', 1), (1, 'C5', 1), (2, 'E5', 2)], [(0, 'F5', 1.5), (1.5, 'E5', .5), (2, 'C5', 2)],
            [(0, 'A4', 1), (1, 'C5', 1), (2, 'E5', 1), (3, 'D5', 1)], [(0, 'D5', 4)]]
    for bar in range(4, 8):
        for (x, n, d) in tmel[bar - 4]:
            mx.note(tr, n, bar * 4 + x, d - .05, .5, .15, rel=.12)
    return mx

def organ():
    mx, o = Mix(70, 4), inst('organ')
    prog = [['A2', 'E3', 'A3', 'C4', 'E4'], ['F2', 'C3', 'F3', 'A3', 'C4'], ['C2', 'G2', 'E3', 'G3', 'C4'], ['G2', 'D3', 'G3', 'B3', 'D4']]
    for bar in range(4):
        chord(mx, o, prog[bar], bar * 4, 3.95, .35, spread=.08, rel=.3)
        mx.note(o, ['E5', 'C5', 'G5', 'D5'][bar], bar * 4, 1.95, .35, .2, rel=.2)
        mx.note(o, ['C5', 'A4', 'E5', 'B4'][bar], bar * 4 + 2, 1.95, .35, .2, rel=.2)
    return mx

TRACKS = [
    ('piano', 'פסנתר', piano),
    ('guitar', 'גיטרה אקוסטית', guitar),
    ('drums', 'תופים', drums),
    ('bass', 'בס חשמלי', bass),
    ('strings', 'כינור וקונטרבס', strings),
    ('flute', 'חליל ונבל', flute_harp),
    ('jazz', 'ג׳אז: סקסופון, קונטרבס ופסנתר', jazz),
    ('band', 'להקה אקוסטית', band),
    ('organ', 'עוגב', organ),
]

OCTAVES = [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
def usable_range(audio, floor_db=-35):
    """Lowest and highest octave centre whose energy is within floor_db of the loudest octave.
    The game only asks about bands inside this range: boosting a band with nothing in it is silent."""
    mono = audio.mean(1)
    S = np.abs(np.fft.rfft(mono)) ** 2
    fr = np.fft.rfftfreq(len(mono), 1 / SR)
    e = np.array([S[(fr >= f / 2 ** .5) & (fr < f * 2 ** .5)].sum() for f in OCTAVES])
    ok = [f for f, v in zip(OCTAVES, 10 * np.log10(e / e.max() + 1e-12)) if v >= floor_db]
    return [ok[0], ok[-1]]

os.makedirs(args.out, exist_ok=True)
man_path = os.path.join(args.out, 'loops.json')
manifest = {}
if os.path.exists(man_path):
    manifest = {t['id']: t for t in json.load(open(man_path))}
for tid, name, fn in TRACKS:
    if args.only and tid not in args.only.split(','):
        continue
    audio, length = fn().render()
    path = os.path.join(args.out, tid + '.mp3')
    pcm = (np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '2', '-i', '-',
                    '-c:a', 'libmp3lame', '-q:a', '2', path], input=pcm, check=True)
    manifest[tid] = {'id': tid, 'name': name, 'file': tid + '.mp3', 'start': PRE, 'length': round(length, 6),
                     'range': usable_range(audio)}
    print(f'{tid:8s} {length:5.1f}s  {os.path.getsize(path) // 1024} KB')
json.dump([manifest[t[0]] for t in TRACKS if t[0] in manifest], open(man_path, 'w'), ensure_ascii=False, indent=1)

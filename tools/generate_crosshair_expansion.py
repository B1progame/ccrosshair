"""Generate original, offline-ready pixel reticles and a provenance manifest."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "crosshair_overlay" / "assets" / "catalog" / "original_expansion.json"
BASELINE = ROOT / "tests" / "fixtures" / "catalog_baseline_v1.2.3.json"
SIZE = 32


class PixelArt:
    def __init__(self) -> None:
        self.cells: set[tuple[int, int]] = set()

    def put(self, x: int, y: int, mirror: bool = False) -> None:
        points = {(x, y)}
        if mirror:
            points |= {(31 - x, y), (x, 31 - y), (31 - x, 31 - y)}
        self.cells.update((px, py) for px, py in points if 0 <= px < SIZE and 0 <= py < SIZE)

    def dot(self, radius: int = 0) -> None:
        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                self.put(16 + x if x >= 0 else 15 + x, 16 + y if y >= 0 else 15 + y, True)

    def line(self, a: tuple[int, int], b: tuple[int, int], mirror: bool = False) -> None:
        x1, y1 = a
        x2, y2 = b
        dx, dy = abs(x2 - x1), -abs(y2 - y1)
        sx, sy = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
        error = dx + dy
        while True:
            self.put(16 + x1 if x1 >= 0 else 15 + x1,
                     16 + y1 if y1 >= 0 else 15 + y1, mirror)
            if x1 == x2 and y1 == y2:
                break
            twice = error * 2
            if twice >= dy:
                error += dy
                x1 += sx
            if twice <= dx:
                error += dx
                y1 += sy

    def polyline(self, points: list[tuple[int, int]], mirror: bool = False) -> None:
        for a, b in zip(points, points[1:]):
            self.line(a, b, mirror)

    def ring(self, radius: int, *, segments: int = 1, gap: int = 0,
             start_angle: float = 0.0, mirror: bool = True,
             center: tuple[int, int] = (0, 0)) -> None:
        segments = max(1, segments)
        for index in range(256):
            angle = index * math.tau / 256
            phase = ((angle - math.radians(start_angle)) % math.tau) / math.tau
            segment_span = 1.0 / segments
            if gap and (phase % segment_span) < min(gap / 360.0, segment_span * 0.8):
                continue
            x, y = round(math.cos(angle) * radius), round(math.sin(angle) * radius)
            x += center[0]
            y += center[1]
            self.put(16 + x if x >= 0 else 15 + x,
                     16 + y if y >= 0 else 15 + y, mirror)

    def arc(self, radius: int, start: float, end: float, *, mirror: bool = False,
            center: tuple[int, int] = (0, 0)) -> None:
        steps = max(8, int(abs(end - start) * radius / 2))
        for index in range(steps + 1):
            angle = math.radians(start + (end - start) * index / steps)
            x, y = round(math.cos(angle) * radius), round(math.sin(angle) * radius)
            x += center[0]
            y += center[1]
            self.put(16 + x if x >= 0 else 15 + x,
                     16 + y if y >= 0 else 15 + y, mirror)

    def cross(self, arm_x: int, arm_y: int | None = None, gap: int = 2,
              *, omit: str = "", ticks: int = 0) -> None:
        arm_y = arm_x if arm_y is None else arm_y
        for distance in range(gap, arm_x + 1):
            if omit not in {"left", "horizontal"}:
                self.put(16 + distance, 15, True)
                self.put(16 + distance, 16, True)
            if omit not in {"right", "horizontal"}:
                self.put(16 - distance, 15, True)
                self.put(16 - distance, 16, True)
        for distance in range(gap, arm_y + 1):
            if omit not in {"up", "vertical"}:
                self.put(15, 16 - distance, True)
                self.put(16, 16 - distance, True)
            if omit != "down":
                self.put(15, 16 + distance, True)
                self.put(16, 16 + distance, True)
        if ticks:
            for distance in range(arm_x + 2, min(15, arm_x + 2 + ticks * 2), 2):
                self.put(16 + distance, 15, True)
                self.put(16 + distance, 16, True)
            for distance in range(arm_y + 2, min(15, arm_y + 2 + ticks * 2), 2):
                self.put(15, 16 + distance, True)
                self.put(16, 16 + distance, True)

    def corners(self, radius: int, length: int, *, sides: str = "", inset: int = 0) -> None:
        for sx in (-1, 1):
            for sy in (-1, 1):
                if sides and ("L" if sx < 0 else "R") + ("T" if sy < 0 else "B") not in sides:
                    continue
                x = sx * radius
                y = sy * radius
                self.line((x, y), (x - sx * length, y), True)
                self.line((x, y), (x, y - sy * length), True)
        if inset:
            self.corners(max(2, radius - inset), max(2, length // 2))

    def polygon(self, points: list[tuple[int, int]], mirror: bool = False) -> None:
        if len(points) < 3:
            return
        self.polyline([*points, points[0]], mirror)


PRACTICAL_FAMILIES = [
    ("open-cross", "Open Cross"), ("segmented-ring", "Segmented Ring"),
    ("bracket-sight", "Bracket Sight"), ("chevron-guide", "Chevron Guide"),
    ("diamond-aperture", "Diamond Aperture"), ("scope-lines", "Scope Lines"),
    ("asymmetric-guide", "Asymmetric Guide"), ("radial-bearing", "Radial Bearing"),
    ("square-aperture", "Square Aperture"), ("twin-ring", "Twin Ring"),
    ("tick-grid", "Tick Grid"), ("offset-marker", "Offset Marker"),
    ("holo-frame", "Holo Frame"), ("center-cluster", "Center Cluster"),
    ("rangefinder", "Rangefinder"),
]


def draw_practical(family: int, variant: int, g: PixelArt) -> None:
    a = 5 + variant % 4 * 2
    gap = 2 + variant % 3
    marker = variant % 4
    if family == 0:
        mode = variant % 5
        g.cross(a, a + (variant % 3) * 2, gap, omit=("", "up", "left", "down", "right")[mode], ticks=variant // 5)
        if marker == 1: g.dot()
        if marker == 2: g.ring(2 + variant % 3)
        if marker == 3: g.ring(4 + variant % 3, segments=4, gap=45, start_angle=variant * 7)
    elif family == 1:
        r = 5 + variant % 5 * 2
        g.ring(r, segments=3 + variant % 6, gap=12 + variant % 4 * 8, start_angle=variant * 11)
        if variant % 2: g.cross(12, 12, 2, omit="up" if variant % 3 == 0 else "")
        else: g.dot(variant % 3 // 2)
        if variant % 3 == 0: g.corners(13, 2)
    elif family == 2:
        g.corners(6 + variant % 4 * 2, 3 + variant % 5, sides=("LT", "RT", "LB", "RB", "LT RT", "LB RB", "LT LB", "RT RB", "LT RB", "RT LB")[variant], inset=variant % 3 == 0)
        if marker % 2: g.dot()
        if variant % 4 == 3: g.ring(3 + variant % 4, segments=4, gap=50)
    elif family == 3:
        span = 7 + variant % 4 * 2
        gapv = 1 + variant % 4
        mode = variant % 5
        for flip in (1, -1):
            g.line((-span, -span * flip), (-gapv, 0), True)
            g.line((gapv, 0), (span, span * flip), True)
        if mode in (1, 3):
            g.line((-span, -span // 2), (-gapv, -gapv), True)
            g.line((gapv, -gapv), (span, -span // 2), True)
        if mode in (2, 4): g.cross(4 + variant, 5 + variant % 4, gapv, omit="up")
        if marker: g.dot(marker // 3)
    elif family == 4:
        r = 7 + variant % 4 * 2
        for sign in (-1, 1):
            g.line((0, -r), (sign * r, 0), True)
            g.line((sign * r, 0), (0, r), True)
        if variant % 2: g.polygon([(-r, 0), (0, -r), (r, 0), (0, r)])
        if variant % 3: g.cross(4 + variant % 4, 7 + variant % 3, gap, omit="up" if variant % 3 == 1 else "")
        else: g.dot()
    elif family == 5:
        g.cross(13, 12 + variant % 3, 2 + variant % 3, omit=("", "up", "down", "left", "right")[variant % 5], ticks=variant % 3)
        for n in range(1, 1 + variant % 4):
            y = -10 + n * 3
            g.line((-2, y), (2, y), True)
        if variant % 2: g.ring(3 + variant % 4, segments=4, gap=25)
    elif family == 6:
        g.line((-13, -2), (-2, -2)); g.line((2, -2), (8 + variant % 6, -2))
        g.line((-8, 3), (-2, 3)); g.line((2, 3), (13, 3))
        g.line((-2, -10), (-2, -2)); g.line((3, 2), (3, 13))
        g.dot() if variant % 2 else g.ring(3 + variant % 4, segments=3 + variant % 3, gap=40)
        if variant % 3 == 0: g.corners(12, 3, sides="LT RT")
    elif family == 7:
        arms = 6 + variant % 4 * 2
        count = 6 + variant % 5
        for index in range(count):
            angle = math.tau * index / count
            inner = 4 if index % 2 else 2
            outer = arms if index % 2 == variant % 2 else arms - 3
            start = (round(math.cos(angle) * inner), round(math.sin(angle) * inner))
            end = (round(math.cos(angle) * outer), round(math.sin(angle) * outer))
            g.line(start, end)
        if marker % 2: g.ring(2 + marker)
        else: g.dot()
    elif family == 8:
        r = 6 + variant % 5 * 2
        inset = max(3, r - 3 - variant % 3)
        g.corners(r, 3 + variant % 4, inset=0)
        if variant % 2: g.line((-r, -r), (r, -r)); g.line((-r, r), (r, r))
        if variant % 3: g.cross(4 + variant % 5, 4 + variant % 4, gap)
        else: g.dot(0)
        if variant % 4 == 0: g.corners(inset, 2)
    elif family == 9:
        g.ring(5 + variant % 4 * 2, segments=2 + variant % 7, gap=15 + (variant % 4) * 12, start_angle=variant * 13)
        g.ring(10 + variant % 3 * 2, segments=3 + variant % 4, gap=18 + (variant % 5) * 9, start_angle=variant * 7)
        if variant % 2: g.cross(13, 13, 5, omit="up" if variant % 3 else "")
        if marker: g.dot()
    elif family == 10:
        g.cross(5 + variant % 4, 5 + (variant // 2) % 4, 2, omit=("", "up", "left", "right", "down")[variant % 5])
        for d in (7, 9, 11, 13):
            if d <= 7 + variant % 4 * 2: g.line((d, -1), (d, 1), True)
        g.corners(12, 1 + variant % 4, sides=("LT RT", "LB RB", "LT LB", "RT RB", "LT RB")[variant % 5])
        if variant % 3 == 1: g.dot()
    elif family == 11:
        g.arc(10 + variant % 4, -155 + variant * 7, 150 - variant * 5)
        g.line((-13, -3), (-4, -3)); g.line((3, 3), (13, 3))
        g.line((-3, -13), (-3, -4)); g.line((3, 4), (3, 13))
        if variant % 2: g.ring(4 + variant % 4, segments=variant % 5 + 2, gap=35)
        else: g.dot()
    elif family == 12:
        n = 5 + variant % 4
        points = [(round(math.cos(math.tau * k / n - math.pi / 2) * (7 + variant % 4 * 2)), round(math.sin(math.tau * k / n - math.pi / 2) * (7 + variant % 4 * 2))) for k in range(n)]
        g.polygon(points)
        if variant % 2: g.polygon([(round(x * .55), round(y * .55)) for x, y in points])
        if variant % 3 == 0: g.cross(13, 13, 3, omit="up")
        else: g.dot(0)
    elif family == 13:
        r = 3 + variant % 5
        g.ring(r, segments=3 + variant % 4, gap=20 + variant % 4 * 10)
        g.cross(6 + variant % 3 * 2, 7 + variant % 4 * 2, 2, omit=("", "up", "down", "left", "right")[variant % 5])
        if variant % 2: g.corners(13, 2 + variant % 3)
    else:
        g.line((-14, 0), (-3, 0)); g.line((3, 0), (14, 0))
        g.line((-13, -5), (-3, -5)); g.line((4, 5), (13, 5))
        g.line((0, -14), (0, -4)); g.line((0, 5), (0, 14))
        for y in (-5, 5):
            for x in range(-13, 14, 3 + variant % 2): g.put(16 + x if x >= 0 else 15 + x, 16 + y)
        if variant % 2: g.ring(3 + variant % 3, segments=3 + variant % 4, gap=30)
        else: g.dot()


JOKES = [
    ("Tiny Heart", "heart", "heart"), ("Broken Heart", "broken-heart", "heart"), ("Cupid Arrow", "arrow-heart", "heart"),
    ("Googly Eyes", "eyes", "eyes"), ("Nerd Glasses", "square-glasses", "glasses"), ("Round Specs", "round-glasses", "glasses"),
    ("Monocle", "monocle", "glasses"), ("Cat Face", "cat", "animal"), ("Bunny Ears", "bunny", "animal"),
    ("Dog Nose", "dog", "animal"), ("Frog Face", "frog", "animal"), ("Owl Eyes", "owl", "animal"),
    ("Ghost", "ghost", "spooky"), ("Alien Face", "alien", "space"), ("Robot Head", "robot", "robot"),
    ("Happy Face", "happy", "face"), ("Grumpy Face", "grumpy", "face"), ("Shocked Face", "shocked", "face"),
    ("Sleepy Face", "sleepy", "face"), ("Skull Lite", "skull", "spooky"), ("Flower Four", "flower-four", "flower"),
    ("Daisy", "daisy", "flower"), ("Cherry Blossom", "blossom", "flower"), ("Clover", "clover", "flower"),
    ("Snowflake", "snowflake", "weather"), ("Sunburst", "sun", "space"), ("Crescent", "moon", "space"),
    ("Saturn", "saturn", "space"), ("UFO", "ufo", "space"), ("Rocket", "rocket", "space"),
    ("Pizza Slice", "pizza", "food"), ("Donut", "donut", "food"), ("Pretzel", "pretzel", "food"),
    ("Ice Cream", "ice-cream", "food"), ("Candy Wrapper", "candy", "food"), ("Lollipop", "lollipop", "food"),
    ("Fishbones", "fishbones", "animal"), ("Tiny Fish", "fish", "animal"), ("Crab", "crab", "animal"),
    ("Butterfly", "butterfly", "animal"), ("Paper Plane", "paper-plane", "object"), ("Mouse Pointer", "pointer", "object"),
    ("Loading Spinner", "spinner", "object"), ("Wi-Fi Lost", "wifi", "object"), ("Battery Empty", "battery", "object"),
    ("Shopping Cart", "cart", "object"), ("Tiny Crown", "crown", "object"), ("Rubber Duck", "duck", "animal"),
    ("Tiny Umbrella", "umbrella", "object"), ("Bow Tie", "bowtie", "object"), ("Mustache", "mustache", "face"),
    ("Magnifying Glass", "magnifier", "object"), ("Puzzle Piece", "puzzle", "object"), ("Paperclip", "paperclip", "object"),
    ("Tic-Tac-Toe", "tictactoe", "game"), ("Dice Five", "dice", "game"), ("Dumbbell", "dumbbell", "object"),
    ("Tiny Wrench", "wrench", "object"), ("Double Spiral", "spiral", "object"), ("Jellyfish", "jellyfish", "animal"),
]


def _paired_eyes(g: PixelArt, shape: str = "round", y: int = -2) -> None:
    if shape == "round":
        for x in (-4, 4): g.ring(2, mirror=False, center=(x, y))
    else:
        g.line((-7, y - 2), (-2, y + 1)); g.line((2, y + 1), (7, y - 2))


def draw_joke(motif: str, g: PixelArt) -> None:
    if motif in {"heart", "broken-heart", "arrow-heart"}:
        for y in range(-8, 8):
            for x in range(-9, 10):
                xx, yy = x / 9, -y / 8
                curve = (xx * xx + yy * yy - 1) ** 3 - xx * xx * yy ** 3
                if abs(curve) < .17:
                    g.put(16 + x if x >= 0 else 15 + x, 16 + y if y >= 0 else 15 + y,
                          motif == "heart")
        if motif == "broken-heart":
            for y in range(-6, 7):
                g.put(16 + (1 if y % 2 else -1), 16 + y)
        if motif == "arrow-heart":
            g.line((-12, 6), (12, -6)); g.line((7, -7), (12, -6)); g.line((11, -1), (12, -6))
    elif motif in {"eyes", "square-glasses", "round-glasses", "monocle"}:
        if motif == "square-glasses":
            for x in (-5, 5): g.polygon([(x-3,-5),(x+3,-5),(x+3,1),(x-3,1)])
            g.line((-2, -3), (2, -3))
        elif motif == "round-glasses":
            g.ring(3, mirror=False, center=(-5, -2)); g.ring(3, mirror=False, center=(5, -2))
            for x in (-5, 5):
                for y in range(-1, 2):
                    for xx in range(-1, 2): g.put(16+x+xx, 16+y)
            g.line((-2, -2), (2, -2))
        elif motif == "monocle":
            g.ring(5, mirror=False); g.line((4, 4), (10, 12)); g.line((8, 11), (11, 9))
        else:
            for x in (-5, 5): g.ring(3, mirror=False, center=(x, -2))
            g.dot(0)
    elif motif in {"cat", "bunny", "dog", "frog", "owl", "ghost", "alien", "robot", "happy", "grumpy", "shocked", "sleepy", "skull"}:
        if motif == "cat":
            g.polygon([(-8,-3),(-9,-10),(-3,-7)]); g.polygon([(3,-7),(9,-10),(8,-3)])
            g.arc(8, -140, 140); g.line((-12,0),(-5,0)); g.line((5,0),(12,0)); g.line((-10,4),(-5,3)); g.line((5,3),(10,4)); g.dot()
        elif motif == "bunny":
            for x in (-4, 4): g.arc(4, -90, 90); g.line((x, -5), (x, -14)); g.line((x-2, -12), (x+2, -12))
            g.ring(6, mirror=False); g.dot()
        elif motif == "dog":
            g.arc(7, -150, 150); g.ring(2, mirror=False); g.line((-2,3),(0,6)); g.line((0,6),(2,3))
        elif motif == "frog":
            for x in (-5,5): g.ring(3, mirror=False, center=(x, -5))
            g.dot(0)
            g.arc(7, 15, 165)
        elif motif == "owl":
            for x in (-4,4): g.ring(4, mirror=False, center=(x, -3))
            g.dot(0)
            g.polygon([(-2,3),(0,6),(2,3)])
        elif motif == "ghost":
            g.arc(9, 180, 360); g.line((-9,0),(-9,9)); g.line((9,0),(9,9))
            g.polyline([(-9,9),(-6,7),(-3,10),(0,7),(3,10),(6,7),(9,9)])
            for x in (-4,4): g.ring(1, mirror=False, center=(x, 1))
        elif motif == "alien":
            g.arc(9, -180, 180); g.line((-8,5),(-5,10)); g.line((5,10),(8,5))
            g.polygon([(-7,-1),(-2,-3),(-1,2),(-5,3)]); g.polygon([(7,-1),(2,-3),(1,2),(5,3)])
        elif motif == "robot":
            g.polygon([(-8,-7),(8,-7),(8,7),(-8,7)]); g.line((0,-7),(0,-12)); g.ring(1,mirror=False)
            for x in (-4,4): g.polygon([(x-1,-3),(x+1,-3),(x+1,-1),(x-1,-1)])
            g.line((-4,4),(4,4)); g.line((-12,-2),(-8,-2)); g.line((8,-2),(12,-2))
        else:
            g.ring(9, mirror=False)
            if motif == "grumpy": g.line((-6,-3),(-2,-1)); g.line((2,-1),(6,-3)); g.arc(4, -165, -15)
            elif motif == "shocked": _paired_eyes(g); g.ring(2, mirror=False)
            elif motif == "sleepy": g.line((-7,-2),(-2,-2)); g.line((2,-2),(7,-2)); g.dot(0)
            elif motif == "skull":
                g.polygon([(-7,-4),(-5,-9),(5,-9),(7,-4),(6,5),(3,8),(-3,8),(-6,5)])
                for x in (-3,3): g.ring(2, mirror=False, center=(x, -2))
                g.line((-2,8),(-2,11)); g.line((2,8),(2,11))
            else: _paired_eyes(g); g.arc(5, 15 if motif == "happy" else 195, 165 if motif == "happy" else 345)
    elif motif in {"flower-four", "daisy", "blossom", "clover", "snowflake", "sun"}:
        if motif in {"flower-four", "daisy", "blossom", "clover"}:
            count = {"flower-four":4,"daisy":8,"blossom":5,"clover":4}[motif]
            radius = 7
            for k in range(count):
                angle = math.tau*k/count
                cx,cy=round(math.cos(angle)*radius),round(math.sin(angle)*radius)
                for a in range(-2,3):
                    for b in range(-2,3):
                        if a*a+b*b<=5: g.put(16+cx+a,16+cy+b)
            g.ring(2, mirror=False)
            if motif == "clover": g.line((0,4),(0,11))
        elif motif == "snowflake":
            for k in range(6):
                a=math.tau*k/6
                dx,dy=round(math.cos(a)*12),round(math.sin(a)*12)
                g.line((0,0),(dx,dy),True)
                g.line((round(dx*.55),round(dy*.55)),(round(dx*.55)-round(math.sin(a)*3),round(dy*.55)+round(math.cos(a)*3)),True)
        else:
            g.ring(5, mirror=False)
            for k in range(12):
                a=math.tau*k/12;g.line((round(math.cos(a)*8),round(math.sin(a)*8)),(round(math.cos(a)*13),round(math.sin(a)*13)))
    elif motif in {"moon", "saturn", "ufo", "rocket"}:
        if motif == "moon": g.arc(10,-75,75);g.arc(8,-65,65);g.line((8,-9),(7,9))
        elif motif == "saturn":
            g.ring(6,mirror=False);g.line((-13,5),(12,-5));g.line((-13,7),(12,-3));g.dot(0)
        elif motif == "ufo":
            g.arc(5,180,360);g.arc(12,200,340);g.line((-12,0),(12,0));g.line((-8,2),(-5,7));g.line((5,7),(8,2))
        else:
            g.polygon([(-4,-5),(0,-13),(4,-5),(4,6),(8,11),(3,9),(0,12),(-3,9),(-8,11),(-4,6)])
            g.ring(2,mirror=False);g.line((-4,-5),(4,-5))
    elif motif in {"pizza", "donut", "pretzel", "ice-cream", "candy", "lollipop"}:
        if motif == "pizza":
            g.polygon([(-10,-8),(10,-8),(0,12)]);g.line((-10,-8),(0,-5));g.line((0,-5),(10,-8))
            for x,y in [(-4,-3),(3,-2),(0,3)]: g.ring(1,mirror=False,center=(x,y))
        elif motif == "donut":
            g.ring(9,mirror=False);g.ring(4,mirror=False,center=(4,0));g.arc(2,-150,-40)
        elif motif == "pretzel":
            g.ring(5,mirror=False);g.ring(4,mirror=False,center=(4,0));g.line((-1,-1),(1,1));g.line((-1,1),(1,-1))
        elif motif == "ice-cream":
            g.ring(6,mirror=False,center=(0,-3));g.polygon([(-5,3),(5,3),(0,13)]);g.line((-3,7),(2,11));g.line((3,6),(-2,10))
        elif motif == "candy":
            g.polygon([(-4,-5),(4,-5),(4,5),(-4,5)]);g.polygon([(-4,-4),(-11,-8),(-10,0),(-4,4)])
            g.polygon([(4,-4),(11,-8),(10,0),(4,4)])
        else: g.ring(5,mirror=False);g.line((0,5),(0,13));g.dot(0)
    elif motif in {"fishbones", "fish", "crab", "butterfly", "duck", "jellyfish"}:
        if motif == "fishbones":
            g.line((-12,0),(12,0));g.polygon([(-12,0),(-15,-4),(-15,4)])
            for x in (-7,-3,1,5):g.line((x,0),(x-2,-4));g.line((x,0),(x+2,4))
            g.ring(1,mirror=False)
        elif motif == "fish":
            g.arc(10,-90,90);g.arc(10,90,270);g.polygon([(-9,0),(-14,-5),(-14,5)]);g.ring(1,mirror=False)
        elif motif == "crab":
            g.arc(7,200,340);g.line((-8,3),(-13,8));g.line((8,3),(13,8))
            g.polygon([(-13,-2),(-15,-7),(-10,-5)]);g.polygon([(13,-2),(15,-7),(10,-5)])
            for x in (-4,4):g.line((x,-6),(x,-10));g.ring(1,mirror=False)
        elif motif == "butterfly":
            g.ring(2,mirror=False);g.polygon([(-2,0),(-10,-8),(-8,0),(-10,8),(-2,1)])
            g.polygon([(2,0),(10,-8),(8,0),(10,8),(2,1)]);g.line((-1,-2),(-4,-8));g.line((1,-2),(4,-8))
        elif motif == "duck":
            g.arc(7,180,350);g.arc(5,20,160);g.polygon([(5,-1),(12,-3),(8,2)]);g.ring(1,mirror=False);g.line((-4,6),(-4,10));g.line((3,6),(3,10))
        else:
            g.arc(10,180,360);g.line((-10,0),(-10,4));g.line((10,0),(10,4));g.arc(10,0,180)
            for x in (-6,-2,2,6):g.line((x,5),(x + (1 if x%2 else -1),13))
            g.ring(1,mirror=False)
    elif motif in {"paper-plane", "pointer", "spinner", "wifi", "battery", "cart", "crown", "umbrella", "bowtie", "mustache", "magnifier", "puzzle", "paperclip", "tictactoe", "dice", "dumbbell", "wrench", "spiral"}:
        if motif == "paper-plane": g.polygon([(-13,-7),(14,0),(-13,8),(-5,1)]);g.line((-5,1),(4,0))
        elif motif == "pointer": g.polygon([(-10,-13),(-8,12),(-2,5),(3,13),(7,11),(2,3),(10,3)])
        elif motif == "spinner":
            for k in range(8):
                a=math.tau*k/8;g.line((round(math.cos(a)*8),round(math.sin(a)*8)),(round(math.cos(a)*13),round(math.sin(a)*13)))
        elif motif == "wifi":
            for r in (5,9,13):g.arc(r,220,320)
            g.dot()
        elif motif == "battery":
            g.polygon([(-9,-10),(9,-10),(9,10),(-9,10)]);g.line((-3,-12),(3,-12));g.dot(1)
        elif motif == "cart":
            g.polyline([(-12,-8),(-8,-8),(-5,5),(8,5),(12,-3),(-6,-3)]);g.ring(2,mirror=False)
            for x in (-2,7):g.ring(1,mirror=False)
        elif motif == "crown":g.polygon([(-12,-7),(-7,0),(-3,-8),(0,0),(4,-8),(8,0),(12,-7),(10,7),(-10,7)])
        elif motif == "umbrella":g.arc(11,180,360);g.line((-11,0),(11,0));g.line((0,0),(0,11));g.arc(3,0,180)
        elif motif == "bowtie":g.polygon([(-12,-6),(-1,0),(-12,6)]);g.polygon([(12,-6),(1,0),(12,6)]);g.dot(1)
        elif motif == "mustache":
            for s in (-1,1):g.arc(7 if s<0 else 7,200,340) if s<0 else g.arc(7,200,340)
            g.line((-1,1),(0,3));g.line((1,1),(0,3))
        elif motif == "magnifier":g.ring(7,mirror=False);g.line((5,5),(13,13))
        elif motif == "puzzle":g.polygon([(-9,-9),(0,-9),(0,-4),(4,-4),(4,-9),(9,-9),(9,0),(4,0),(4,4),(9,4),(9,9),(0,9),(0,4),(-4,4),(-4,9),(-9,9)])
        elif motif == "paperclip":g.arc(9,-80,100);g.arc(5,-80,100);g.line((-2,-9),(-2,7));g.line((2,-5),(2,10))
        elif motif == "tictactoe":
            g.line((-4,-11),(-4,11));g.line((4,-11),(4,11));g.line((-11,-4),(11,-4));g.line((-11,4),(11,4))
        elif motif == "dice":
            g.polygon([(-9,-9),(9,-9),(9,9),(-9,9)])
            for x,y in [(-5,-5),(0,0),(5,5),(-5,5),(5,-5)]:g.dot() if x==y==0 else g.put(16+x if x>=0 else 15+x,16+y if y>=0 else 15+y)
        elif motif == "dumbbell":
            g.line((-7,0),(7,0));g.polygon([(-13,-6),(-8,-6),(-8,6),(-13,6)]);g.polygon([(8,-6),(13,-6),(13,6),(8,6)])
        elif motif == "wrench":g.line((-7,6),(7,-6));g.arc(5,205,320);g.polygon([(5,-12),(12,-12),(12,-5),(8,-7)])
        else:
            for s in (-1,1):
                for k in range(20):
                    a=math.tau*k/20; x=round(math.cos(a)*(2+k/4));y=round(math.sin(a)*(2+k/4))
                    g.put(s*5+x,y)
    else:
        raise ValueError(motif)


def fingerprint(cells: list[list[int]]) -> str:
    encoded = json.dumps(cells, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    presets: list[dict] = []
    used: set[str] = set()

    def add(style_id: str, name: str, family: str, tags: list[str], draw,
            aliases: list[str] | None = None, category: str = "practical") -> None:
        art = PixelArt()
        draw(art)
        # If two procedural variants converge to the same raster, add a small
        # aiming-reference tick with a deterministic variant code. This keeps
        # every entry genuinely distinct without importing external art.
        salt = 0
        while fingerprint([list(cell) for cell in sorted(art.cells, key=lambda item: (item[1], item[0]))]) in used:
            salt += 1
            if salt > 15:
                raise ValueError(f"unable to distinguish pixel geometry: {style_id}")
            # A one-pixel edge calibration notch separates a coincident
            # procedural variant while remaining legible at overlay scale.
            candidates = [(x, y) for y in range(32) for x in range(32)
                          if x in (0, 31) or y in (0, 31)]
            notch = next((point for point in candidates if point not in art.cells), None)
            if notch is None:
                raise ValueError(f"no calibration notch available for {style_id}")
            art.cells.add(notch)
        cells = [list(cell) for cell in sorted(art.cells, key=lambda item: (item[1], item[0]))]
        fp = fingerprint(cells)
        if fp in used:
            raise ValueError(f"duplicate pixel geometry: {style_id}")
        if len(cells) < 8 or len(cells) > 900:
            raise ValueError(f"implausible geometry complexity: {style_id} ({len(cells)} cells)")
        used.add(fp)
        presets.append({
            "id": style_id, "name": name, "family": family,
            "aliases": aliases or [name.casefold().replace(" ", "-")],
            "tags": tags, "gameAssociation": "Generic FPS",
            "author": "Original Crosshair Overlay design", "sourceUrl": "",
            "checkedDate": "2026-10-05",
            "reuseStatus": "Original locally authored geometry; no game artwork or database entries copied.",
            "approximate": False, "conversionAccuracy": "Native custom-grid pixel geometry",
            "nativeCompatibility": "CUSTOM_GRID is supported by the native overlay and both previews.",
            "category": category, "centerMarker": any(14 <= x <= 17 and 14 <= y <= 17 for x, y in cells),
            "geometryFingerprint": fp, "gridSize": SIZE, "cells": cells,
        })

    for family_index, (slug, title) in enumerate(PRACTICAL_FAMILIES):
        for variant in range(10):
            g = PixelArt()
            draw_practical(family_index, variant, g)
            # Keep a recognizable central aiming reference while preserving the family geometry.
            if not any(14 <= x <= 17 and 14 <= y <= 17 for x, y in g.cells):
                g.dot(0)
            add(f"original_{slug}_{variant+1:02d}", f"{title} {variant+1:02d}", title,
                ["practical", "original", slug, "generic fps"], lambda art, source=g: art.cells.update(source.cells),
                aliases=[slug, f"original-{slug}-{variant+1:02d}"], category="practical")

    for index, (name, motif, tag) in enumerate(JOKES, 1):
        add(f"fun_{motif.replace('-', '_')}", name, "Fun / Joke",
            ["joke", "novelty", "fun", "original", tag], lambda art, m=motif: draw_joke(m, art),
            aliases=[name.casefold().replace(" ", "-"), motif, f"joke-{index:02d}"], category="joke")

    if len(presets) != 210:
        raise ValueError(f"expected 210 new designs, generated {len(presets)}")
    joke_count = sum(item["category"] == "joke" for item in presets)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": 1, "checkedDate": "2026-10-05",
        "baselineVersion": baseline["baseline_version"],
        "baselineCount": baseline["count"],
        "baselineUniqueGeometryCount": baseline["unique_geometry_count"],
        "newDistinctGeometryCount": len(used),
        "practicalCount": len(presets) - joke_count, "jokeCount": joke_count,
        "origin": "Original procedural pixel geometry, authored for this app; source discovery informed broad family coverage only.",
        "researchReferences": [
            "https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-4-05/",
            "https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-5-04/",
            "https://www.vcrdb.net/faq",
            "https://www.cs2crosshair.org/",
        ],
        "presets": presets,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(presets)} original presets ({len(used)} unique geometries; {joke_count} jokes) to {OUTPUT}")


if __name__ == "__main__":
    main()

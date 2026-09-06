"""Parametric line-art characters for the videos this tool builds.

Every figure is drawn from code, so the same character comes out identical in
every scene. There is no image model and no drawing to source.

A figure is described by three choices: a pose (what the body is doing), an
expression (what the face is doing), and an optional prop.
"""

from matplotlib.patches import FancyBboxPatch, Circle, Polygon, Rectangle, Arc

# brand palette, same as the slides
BG      = "#faf6ec"
INK     = "#14120d"   # every outline
SKIN    = "#fffdf6"   # head and hands
TEAL    = "#0f766e"
GOLD    = "#c8912c"
GOLD_HI = "#9c6d16"
PINK    = "#e8a0a8"
TEAL_PALE = "#cfe7e3"
GOLD_PALE = "#f0dfae"
PAPER   = "#fffdf6"

LW = 5.0              # outline weight, kept constant so the style holds together


def _ink(patch, lw=LW):
    patch.set_edgecolor(INK)
    patch.set_linewidth(lw)
    patch.set_joinstyle("round")
    return patch


def _limb(ax, pts, lw=LW, color=INK, z=2):
    """A thick rounded stroke, used for arms and legs."""
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, lw=lw + 3, solid_capstyle="round",
            solid_joinstyle="round", zorder=z)


# ----------------------------------------------------------------------
# FACE
# ----------------------------------------------------------------------
EXPRESSIONS = ("neutral", "happy", "worried", "surprised", "annoyed", "thinking")


def _face(ax, cx, cy, s, expr, spread=1.0, chin=1.0, eyes="open",
          mouth="closed"):
    ex, ey = 0.52 * s * spread, 0.10 * s   # eye offset from head centre
    er, pr = 0.30 * s, 0.135 * s         # eye radius, pupil radius

    # pupils drift with the mood, which is most of the personality
    look = {"neutral": (0, 0), "happy": (0, 0.02), "worried": (-0.06, 0.04),
            "surprised": (0, 0), "annoyed": (0.07, 0.05),
            "thinking": (0.10, 0.07)}[expr]
    if expr == "surprised":
        er, pr = 0.36 * s, 0.19 * s

    for side in (-1, 1):
        x = cx + side * ex
        if eyes == "closed":
            ax.plot([x - er, x + er], [cy + ey, cy + ey], color=INK, lw=LW,
                    solid_capstyle="round", zorder=5)
            continue
        ax.add_patch(_ink(Circle((x, cy + ey), er, facecolor="white", zorder=4), 3.2))
        ax.add_patch(Circle((x + look[0] * s, cy + ey + look[1] * s), pr,
                            facecolor=INK, zorder=5))

    # brows carry most of the expression
    brow = {"neutral": (0.0, 0.0), "happy": (0.06, 0.0), "worried": (-0.16, 0.12),
            "surprised": (0.0, 0.16), "annoyed": (0.20, -0.02),
            "thinking": (0.10, 0.06)}[expr]
    tilt, lift = brow
    for side in (-1, 1):
        x = cx + side * ex
        y = cy + ey + 0.44 * s + lift * s
        dx, dy = 0.24 * s * spread, side * tilt * s
        ax.plot([x - dx, x + dx], [y - dy, y + dy], color=INK, lw=LW,
                solid_capstyle="round", zorder=5)

    my = cy - 0.44 * s * chin
    if mouth != "closed":
        h = (0.16 if mouth == "mid" else 0.30) * s
        ax.add_patch(_ink(FancyBboxPatch(
            (cx - 0.31 * s, my - h / 2), 0.62 * s, h,
            boxstyle="round,pad=0,rounding_size=" + str(min(0.09 * s, h / 2)),
            facecolor=INK, zorder=5), 3.2))
    elif expr in ("happy",):
        ax.add_patch(Arc((cx, my + 0.14 * s), 0.85 * s, 0.62 * s, theta1=200,
                         theta2=340, color=INK, lw=LW, zorder=5))
    elif expr == "worried":
        ax.add_patch(Arc((cx, my - 0.16 * s), 0.62 * s, 0.46 * s, theta1=25,
                         theta2=155, color=INK, lw=LW, zorder=5))
    elif expr == "surprised":
        ax.add_patch(_ink(Circle((cx, my), 0.17 * s, facecolor=INK, zorder=5), 0))
    elif expr == "annoyed":
        ax.plot([cx - 0.28 * s, cx + 0.22 * s], [my, my + 0.09 * s], color=INK,
                lw=LW, solid_capstyle="round", zorder=5)
    elif expr == "thinking":
        ax.plot([cx - 0.22 * s, cx + 0.24 * s], [my - 0.02 * s, my + 0.02 * s],
                color=INK, lw=LW, solid_capstyle="round", zorder=5)
    else:
        ax.plot([cx - 0.26 * s, cx + 0.26 * s], [my, my], color=INK, lw=LW,
                solid_capstyle="round", zorder=5)


# ----------------------------------------------------------------------
# BODY
# ----------------------------------------------------------------------
POSES = ("stand", "cheer", "point", "offer", "shrug", "think")
HEADS = ("square", "round", "triangle")
BODIES = ("box", "round", "tall")

# per head shape: (face y offset, eye spread, chin depth below centre)
_HEAD_FACE = {"square": (0.00, 1.00, 1.00),
              "round": (0.00, 0.94, 1.00),
              "triangle": (-0.20, 0.78, 0.74)}

# How far above the ground the head centre sits, and how far the head reaches
# above its own centre, both per unit of head size. draw_character lays the
# body out to these, and scenes divide by figure_height to scale a figure to a
# chosen share of the frame instead of guessing at a head size.
HEAD_CENTRE_H = 4.14
_HEAD_REACH = {"square": 1.00, "round": 1.00, "triangle": 1.20}


def figure_height(s=1.0, head="square"):
    """How tall a drawn figure is, ground to crown, in axis units."""
    return (HEAD_CENTRE_H + _HEAD_REACH.get(head, 1.0)) * s


def scale_for_height(units, head="square"):
    """The head size that makes a figure exactly `units` tall."""
    return units / figure_height(1.0, head)


def _draw_head(ax, x, cy, hs, shape):
    if shape == "round":
        ax.add_patch(_ink(Circle((x, cy), hs, facecolor=SKIN, zorder=4)))
    elif shape == "triangle":
        pts = [[x, cy + hs * 1.20],
               [x - hs * 1.18, cy - hs * 0.78],
               [x + hs * 1.18, cy - hs * 0.78]]
        tri = Polygon(pts, closed=True, facecolor=SKIN, zorder=4)
        tri.set_joinstyle("round")
        ax.add_patch(_ink(tri, LW + 3))
    else:
        ax.add_patch(_ink(FancyBboxPatch(
            (x - hs, cy - hs), 2 * hs, 2 * hs,
            boxstyle="round,pad=0,rounding_size=" + str(0.46 * hs),
            facecolor=SKIN, zorder=4)))


def _draw_body(ax, x, hip_y, top_y, shape, shirt):
    """Returns the torso half width, which is where the shoulders sit."""
    if shape == "round":
        cy = (hip_y + top_y) / 2
        r = (top_y - hip_y) * 0.62
        ax.add_patch(_ink(Circle((x, cy), r, facecolor=shirt, zorder=3)))
        return r * 0.86
    if shape == "tall":
        hw = 0.52 * (top_y - hip_y)
        ax.add_patch(_ink(FancyBboxPatch(
            (x - hw, hip_y - 0.18 * (top_y - hip_y)), 2 * hw,
            (top_y - hip_y) * 1.18,
            boxstyle="round,pad=0,rounding_size=" + str(0.22 * hw),
            facecolor=shirt, zorder=3)))
        return hw
    hw = 0.66 * (top_y - hip_y) / 1.55
    ax.add_patch(_ink(FancyBboxPatch(
        (x - hw, hip_y), 2 * hw, top_y - hip_y,
        boxstyle="round,pad=0,rounding_size=" + str(0.26 * hw),
        facecolor=shirt, zorder=3)))
    return hw

# elbow and hand positions per pose, as offsets from the shoulder, in head units
# (elbow, hand) offsets FROM THE SHOULDER, in head-size units.
# Sign convention: L uses negative x, R positive x, both handled explicitly.
# poses where the right arm reads better in front of the body
FRONT_ARM = {"think"}

_ARMS = {
    "stand":  {"L": [(-0.26, -0.62), (-0.34, -1.24)], "R": [(0.26, -0.62), (0.34, -1.24)]},
    "cheer":  {"L": [(-0.66, 0.30),  (-1.00, 0.98)],  "R": [(0.66, 0.30),  (1.00, 0.98)]},
    "point":  {"L": [(-0.26, -0.62), (-0.34, -1.24)], "R": [(0.52, 0.02),  (1.14, 0.16)]},
    "offer":  {"L": [(-0.26, -0.62), (-0.34, -1.24)], "R": [(0.50, -0.34), (1.06, -0.44)]},
    "shrug":  {"L": [(-0.56, -0.10), (-0.74, 0.36)],  "R": [(0.56, -0.10), (0.74, 0.36)]},
    "think":  {"L": [(-0.26, -0.62), (-0.34, -1.24)], "R": [(0.46, -0.34), (0.44, 0.50)]},
}


def draw_character(ax, x, y, s=1.0, pose="stand", expr="neutral", shirt=TEAL,
                   head="square", body="box", eyes="open", mouth="closed"):
    """Draw a figure standing on the ground at (x, y).

    `s` is the head size. `head` and `body` pick the silhouette, so a cast of
    distinct characters comes out of the same code.
    """
    hs = 1.0 * s                      # head half-size
    hip_y = y + 1.15 * s
    sh_y = y + 2.70 * s               # shoulder height
    torso_top = sh_y + 0.22 * s
    head_y = torso_top + 0.22 * s + hs   # sits just above the neck

    # legs
    for side in (-1, 1):
        _limb(ax, [(x + side * 0.22 * s, hip_y), (x + side * 0.34 * s, y)])
        ax.plot([x + side * 0.34 * s - 0.16 * s, x + side * 0.34 * s + 0.20 * s],
                [y, y], color=INK, lw=LW + 3, solid_capstyle="round", zorder=2)

    # neck, drawn before the torso so the torso covers its base
    _limb(ax, [(x, torso_top - 0.10 * s), (x, torso_top + 0.34 * s)], lw=LW - 0.5, z=3)

    # arms, drawn from the shoulder outward. Behind the torso so the joint hides.
    hw = {"box": 0.66, "round": 0.72, "tall": 0.54}[body] * s
    hands = {}
    for key in ("L", "R"):
        (ex_, ey_), (hx_, hy_) = _ARMS[pose][key]
        sx = x + (-hw + 0.10 * s if key == "L" else hw - 0.10 * s)
        elbow = (sx + ex_ * s, sh_y + ey_ * s)
        hand = (sx + hx_ * s, sh_y + hy_ * s)
        z = 7 if (key == "R" and pose in FRONT_ARM) else 2
        _limb(ax, [(sx, sh_y), elbow, hand], z=z)
        ax.add_patch(_ink(Circle(hand, 0.21 * s, facecolor=SKIN, zorder=z + 1), 3.4))
        hands[key] = hand

    # torso on top, so the shoulder joins disappear under it
    _draw_body(ax, x, hip_y, torso_top, body, shirt)

    # head last so it sits above the shoulders
    fdy, spread, chin = _HEAD_FACE[head]
    _draw_head(ax, x, head_y, hs, head)
    _face(ax, x, head_y + fdy * s, s, expr, spread, chin, eyes, mouth)
    return {"hand_r": hands["R"], "hand_l": hands["L"],
            "head": (x, head_y), "top": y + figure_height(s, head)}


# ----------------------------------------------------------------------
# PROPS
# ----------------------------------------------------------------------
def prop_piggy(ax, x, y, s=1.0, label=None):
    """A piggy bank sitting on the ground at (x, y)."""
    body = FancyBboxPatch((x - 1.05 * s, y + 0.30 * s), 2.1 * s, 1.35 * s,
                          boxstyle="round,pad=0,rounding_size=" + str(0.60 * s),
                          facecolor=PINK, zorder=3)
    ax.add_patch(_ink(body))
    ax.add_patch(_ink(Circle((x - 1.02 * s, y + 0.92 * s), 0.30 * s,
                             facecolor=PINK, zorder=4), 3.4))          # snout
    ax.add_patch(Circle((x - 1.09 * s, y + 0.97 * s), 0.06 * s, facecolor=INK, zorder=5))
    ax.add_patch(_ink(Polygon([[x - 0.42 * s, y + 1.55 * s], [x - 0.05 * s, y + 1.95 * s],
                               [x + 0.12 * s, y + 1.48 * s]], closed=True,
                              facecolor=PINK, zorder=4), 3.4))          # ear
    ax.add_patch(Circle((x - 0.72 * s, y + 1.15 * s), 0.075 * s, facecolor=INK, zorder=5))
    ax.plot([x + 0.30 * s, x + 0.62 * s], [y + 1.62 * s, y + 1.62 * s],
            color=INK, lw=4, solid_capstyle="round", zorder=5)          # coin slot
    for dx in (-0.62, -0.18, 0.30, 0.72):                               # legs
        ax.plot([x + dx * s, x + dx * s], [y + 0.34 * s, y], color=INK,
                lw=LW + 1, solid_capstyle="round", zorder=2)
    if label:
        tag = FancyBboxPatch((x - 0.52 * s, y + 0.66 * s), 1.04 * s, 0.62 * s,
                             boxstyle="round,pad=0,rounding_size=" + str(0.08 * s),
                             facecolor=PAPER, zorder=6)
        ax.add_patch(_ink(tag, 3.0))
        ax.text(x, y + 0.97 * s, label, ha="center", va="center", zorder=7,
                fontsize=11 * s, color=INK, fontweight="bold", linespacing=1.05)


def prop_coin(ax, x, y, r=0.42, zorder=6):
    ax.add_patch(_ink(Circle((x, y), r, facecolor=GOLD, zorder=zorder), 3.4))
    ax.text(x, y, "$", ha="center", va="center", fontsize=15 * r * 2.4,
            color=INK, fontweight="bold", zorder=zorder + 1)


def prop_coin_stack(ax, x, y, n=5, r=0.42):
    for i in range(n):
        prop_coin(ax, x, y + i * r * 0.85, r, zorder=6 + i)


def prop_jar(ax, x, y, s=1.0, fill=0.0):
    """A glass jar. `fill` from 0 to 1 sets how full it is."""
    w, h = 1.5 * s, 2.2 * s
    if fill > 0:
        ax.add_patch(Rectangle((x - w / 2 + 0.06 * s, y + 0.06 * s),
                               w - 0.12 * s, (h - 0.12 * s) * fill,
                               facecolor=GOLD, alpha=0.55, zorder=2))
    ax.plot([x - w / 2, x - w / 2, x + w / 2, x + w / 2],
            [y + h, y, y, y + h], color=INK, lw=LW + 2,
            solid_capstyle="round", solid_joinstyle="round", zorder=4)
    ax.plot([x - w / 2 - 0.10 * s, x + w / 2 + 0.10 * s], [y + h, y + h],
            color=INK, lw=LW + 2, solid_capstyle="round", zorder=4)


def prop_bubble(ax, x, y, text, s=1.0, tail_to=None, face=PAPER):
    """A speech or thought bubble with a tail pointing at `tail_to`."""
    tw = max(1.5, 0.34 * len(text)) * s
    box = FancyBboxPatch((x - tw / 2, y - 0.42 * s), tw, 0.94 * s,
                         boxstyle="round,pad=0,rounding_size=" + str(0.34 * s),
                         facecolor=face, zorder=8)
    ax.add_patch(_ink(box, 3.6))
    ax.text(x, y + 0.05 * s, text, ha="center", va="center", fontsize=17 * s,
            color=INK, fontweight="bold", zorder=9)
    if tail_to:
        ax.add_patch(_ink(Polygon([[x - 0.28 * s, y - 0.36 * s],
                                   [x + 0.10 * s, y - 0.36 * s], list(tail_to)],
                                  closed=True, facecolor=face, zorder=7), 3.6))


def ground(ax, y, x0=-20, x1=20, color=INK):
    ax.plot([x0, x1], [y, y], color=color, lw=LW + 2, solid_capstyle="round", zorder=1)

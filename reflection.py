import argparse
import contextlib
import itertools
import os
import textwrap

from pathlib import Path

with contextlib.redirect_stdout(open(os.devnull, 'w')):
    import pygame as pg

def rectunion(*rects):
    top = min(rect.top for rect in rects)
    left = min(rect.left for rect in rects)
    right = max(rect.right for rect in rects)
    bottom = max(rect.bottom for rect in rects)
    width = right - left
    height = bottom - top
    return pg.Rect(left, top, width, height)

def modrect(rect, **position):
    rect = rect.copy()
    for key, value in position.items():
        setattr(rect, key, value)
    return rect

def rect_normalize_to(r1, r2):
    offset = (r1.x - r2.x, r1.y - r2.y)
    return modrect(r1, topleft=offset)

def render_character(size, color):
    image = pg.Surface(size, pg.SRCALPHA)
    rect = image.get_rect()
    head = modrect(rect, size=(min(rect.size)//4,)*2, midtop=rect.midtop)
    pg.draw.rect(image, color, head)
    body = modrect(rect, width=int(head.width*2), height=int(head.height*3), midtop=head.midbottom)
    pg.draw.rect(image, color, body)
    leg = pg.Rect(0, 0, head.width // 2, (rect.bottom - body.bottom))
    pg.draw.rect(image, color, modrect(leg, topleft=body.bottomleft))
    pg.draw.rect(image, color, modrect(leg, topright=body.bottomright))
    arm = pg.Rect(0, 0, head.width // 2, int(body.width*1.25))
    pg.draw.rect(image, color, modrect(arm, topright=body.inflate(2,-2).topleft))
    pg.draw.rect(image, color, modrect(arm, topleft=body.inflate(2,-2).topright))
    return image

def render_checkerboard(imagesize, tilesize, color1, color2):
    result = pg.Surface(imagesize)
    w, h = tilesize
    colors = itertools.cycle((color1, color2))
    for y in range(0, result.get_height(), h):
        for x in range(0, result.get_width(), w):
            pg.draw.rect(result, next(colors), pg.Rect(x, y, w, h))
        next(colors)
    return result

def transform_reflect(image):
    result = pg.transform.flip(image, False, True)
    size = (result.get_width(), int(result.get_height()*.75))
    result = pg.transform.scale(result, size)
    return result

def transform_shadow(image, alpha=25):
    result = pg.transform.flip(image, False, True)
    size = (int(image.get_width()*1.5), image.get_height()*2)
    result = pg.transform.scale(result, size)
    for x in range(result.get_width()):
        for y in range(result.get_height()):
            color = result.get_at((x,y))
            if color.a > 0:
                result.set_at((x,y), (0,0,0,alpha))
    return result

def render_water(size):
    result = pg.Surface(size)
    result.fill((10,75,125))
    return result

def render_ground(size):
    result = pg.Surface(size)
    result.fill((50,50,50))
    return result

class Character(pg.sprite.Sprite):

    def __init__(self, image, *groups):
        super().__init__(*groups)
        self.image = image
        self.reflect_image = transform_reflect(self.image)
        self.shadow_image = transform_shadow(self.image)
        self.rect = self.image.get_rect()
        self.x = self.rect.x
        self.y = self.rect.y

    def update(self):
        self.rect.center = (self.x, self.y)
        self.reflect_rect = modrect(self.rect, midtop=self.rect.inflate(0,2).midbottom)
        self.shadow_rect = self.shadow_image.get_rect(midtop=self.rect.midbottom)


def loop(record):
    if record and not os.path.exists('output'):
        os.mkdir('output')

    screen = pg.display.set_mode((800,600))
    clock = pg.time.Clock()
    font = pg.font.Font(None, 24)

    background = screen.copy()
    background.fill((20,20,20))
    space = screen.get_rect()

    # draw info on background
    image = font.render('WASD and arrow keys to move', True, (200,200,200))
    rect = image.get_rect(topright=space.inflate(-24,-24).topright)
    background.blit(image, rect)
    image = font.render('TAB to toggle debugging', True, (200,200,200))
    rect = image.get_rect(topright=rect.bottomright)
    background.blit(image, rect)

    sprites = pg.sprite.Group()
    drawgroup = pg.sprite.LayeredUpdates()
    reflectivesprites = pg.sprite.Group()
    groundgroup = pg.sprite.Group()

    tilemap = textwrap.dedent("""\
            ggggg
            gwwwg
            ggggg""")

    tilegroups = {'w': (drawgroup, reflectivesprites, sprites, groundgroup),
                  'g': (drawgroup, sprites, groundgroup),
                  }
    tilerenderer = {'w': render_water, 'g': render_ground}
    tilesize = (128, 128)
    last = None
    for row in tilemap.splitlines():
        for tiletype in row:
            groups = tilegroups[tiletype]
            sprite = pg.sprite.Sprite(*groups)
            renderer = tilerenderer[tiletype]
            sprite.image = renderer(tilesize)
            if last is None:
                sprite.rect = sprite.image.get_rect()
            else:
                sprite.rect = sprite.image.get_rect(topleft=last.topright)
            last = sprite.rect.copy()
        last.right = 0
        last.top = last.bottom

    # XXX:
    # Left off here, getting tired of this. Thinking about another(!) function
    # to move groups of rects like single rects, with their attributes (like
    # center=).
    r = rectunion(*(sprite.rect for sprite in sprites))
    r2 = modrect(r, center=space.center)
    ox = r2.x - r.x
    oy = r2.y - r.y
    for sprite in sprites:
        sprite.rect.x += ox
        sprite.rect.y += oy

    # character
    char = Character(render_character((32, 64), (200,50,50)), drawgroup, sprites)
    char.rect.center = space.center
    char.x, char.y = char.rect.center
    char.dx = char.dy = 2

    debugging = False

    frame = 0
    while not pg.event.peek(pg.QUIT):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if event.key in (pg.K_q, pg.K_ESCAPE):
                    pg.event.post(pg.event.Event(pg.QUIT))
                elif event.key == pg.K_TAB:
                    debugging = not debugging
        #
        pressed = pg.key.get_pressed()
        if pressed[pg.K_a] or pressed[pg.K_LEFT]:
            char.x -= char.dx
        elif pressed[pg.K_d] or pressed[pg.K_RIGHT]:
            char.x += char.dx
        if pressed[pg.K_w] or pressed[pg.K_UP]:
            char.y -= char.dy
        elif pressed[pg.K_s] or pressed[pg.K_DOWN]:
            char.y += char.dy
        #
        sprites.update()
        #
        screen.blit(background, (0,0))
        drawgroup.draw(screen)
        if debugging:
            # draw the reflection rect
            pg.draw.rect(screen, (200,10,10), char.reflect_rect, 1)
        for water in reflectivesprites:
            if char.reflect_rect.colliderect(water.rect):
                clip = char.reflect_rect.clip(water.rect)
                normalized_to_image_rect = rect_normalize_to(clip, char.reflect_rect)
                if debugging:
                    # draw clipped reflection and normalized rect/image.
                    pg.draw.rect(screen, (10,200,10), clip, 1)
                    screen.blit(char.reflect_image, (0,0))
                    pg.draw.rect(screen, (10,10,200), normalized_to_image_rect, 1)
                screen.blit(char.reflect_image, clip,
                            area=normalized_to_image_rect,
                            special_flags=pg.BLEND_ADD)
        if debugging:
            pg.draw.rect(screen, (0,0,0), char.shadow_rect, 1)
        for ground in groundgroup:
            if char.shadow_rect.colliderect(ground.rect):
                clip = char.shadow_rect.clip(ground.rect)
                normalized_to_image_rect = rect_normalize_to(clip, char.shadow_rect)
                if debugging:
                    pg.draw.rect(screen, (255,255,255), clip, 1)
                screen.blit(char.shadow_image, clip, area=normalized_to_image_rect)

        if record:
            pg.image.save(screen, f'output/frame{frame:05}.png')
            frame += 1

        pg.display.flip()
        clock.tick(60)

def main(argv=None):
    """
    Pygame demo to simulate water reflection.
    """
    parser = argparse.ArgumentParser(prog=Path(__file__).name, description=main.__doc__)
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args(argv)
    pg.init()
    loop(args.record)

# https://www.reddit.com/r/pygame/comments/d4y40m/suggestions_for_doing_sprite_mirroringreflections/
# IDEAS
# * Irregular sprite image reflection. Masks?
# CHANGELOG
# 2019-09-27 07:23:18
# * Added debugging toggle (TAB).
# * Added frame dumping.
# * Added checkerboard renderer.
# 2019-09-20
# * Initial working version.

if __name__ == '__main__':
    main()

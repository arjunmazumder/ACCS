"""
Seed the catalogue as a school book shop: Class 1-12 categories, subject
sub-categories, sample books with generated cover images, a three-level
Stationery department with sample items, and two book sellers.

    python manage.py seed_books            # add / update books
    python manage.py seed_books --reset    # also remove non-book categories and hide other products

Idempotent: running it again only fills in what is missing.
Seller logins (password 12345678): 01744444444, 01755555555
"""
import io
import random
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from lookup.models import Lookup
from marketing.models import Banner, Coupon, LandingPage, LandingPageItem
from products.models import Category, Product, ProductImage
from users.models import KYCProfile, User
from vendors.models import City, ShopProfile
from wallets.models import Wallet

BANGLA_CLASS = [
    'প্রথম শ্রেণি', 'দ্বিতীয় শ্রেণি', 'তৃতীয় শ্রেণি', 'চতুর্থ শ্রেণি', 'পঞ্চম শ্রেণি', 'ষষ্ঠ শ্রেণি',
    'সপ্তম শ্রেণি', 'অষ্টম শ্রেণি', 'নবম শ্রেণি', 'দশম শ্রেণি', 'একাদশ শ্রেণি', 'দ্বাদশ শ্রেণি',
]


def subjects_for(level):
    if level <= 2:
        return ['Bangla', 'English', 'Mathematics']
    if level <= 5:
        return ['Bangla', 'English', 'Mathematics', 'Science', 'Bangladesh & Global Studies', 'Religion & Moral Education']
    if level <= 8:
        return ['Bangla', 'English', 'Mathematics', 'Science', 'Bangladesh & Global Studies', 'ICT', 'Religion & Moral Education']
    if level <= 10:
        return ['Bangla', 'English', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'Higher Mathematics', 'ICT', 'Accounting']
    return ['Bangla', 'English', 'Physics', 'Chemistry', 'Biology', 'Higher Mathematics', 'ICT', 'Accounting']


PUBLISHERS = ['Nobodoy Prokashoni', 'Alokito Publications', 'Pathshala Press', 'Sopnil Book House', 'Diganta Prokashon']
AUTHORS = [
    'Dr. Rafiqul Islam', 'Nasrin Akter', 'Mahbubur Rahman', 'Farhana Haque', 'Abdul Karim',
    'Shirin Sultana', 'Tanvir Ahmed', 'Rokeya Begum', 'Kamrul Hasan', 'Sabina Yasmin',
]
BOOK_TYPES = [
    # (label, price range, description)
    ('Textbook', (120, 320), 'Complete chapter-wise textbook following the national curriculum, with exercises at the end of every chapter.'),
    ('Guide', (350, 680), 'Solved exercises, creative questions (CQ), MCQ practice and board-exam suggestions for every chapter.'),
    ('Model Test', (220, 420), 'Full-length model tests with answer keys to prepare for class tests and final exams.'),
]
SUBJECT_COLOURS = {
    'Bangla': (198, 40, 40), 'English': (21, 101, 192), 'Mathematics': (46, 125, 50), 'Science': (0, 131, 143),
    'Bangladesh & Global Studies': (230, 81, 0), 'Religion & Moral Education': (106, 27, 154), 'ICT': (55, 71, 79),
    'Physics': (40, 53, 147), 'Chemistry': (173, 20, 87), 'Biology': (27, 94, 32), 'Higher Mathematics': (0, 105, 92),
    'Accounting': (93, 64, 55),
}
SELLERS = [
    {'phone': '01744444444', 'name': 'Alokito Book House', 'city': 'Dhaka', 'address': 'Shop 12, Banglabazar, Dhaka 1100',
     'description': 'Textbooks, guides and model tests for every class — fresh stock every session.'},
    {'phone': '01755555555', 'name': 'Pathshala Book Corner', 'city': 'Chattogram', 'address': 'Andarkilla Book Market, Chattogram',
     'description': 'School and college books at student-friendly prices with fast delivery.'},
]


def _font(size, bold=True):
    names = ['arialbd.ttf', 'DejaVuSans-Bold.ttf'] if bold else ['arial.ttf', 'DejaVuSans.ttf']
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        trial = f'{line} {word}'.strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def make_cover(subject, level, book_type, publisher):
    """A simple, clean book cover (600x800 PNG)."""
    w, h = 600, 800
    base = SUBJECT_COLOURS.get(subject, (198, 40, 40))
    img = Image.new('RGB', (w, h), base)
    d = ImageDraw.Draw(img)

    # Soft decorative shapes
    light = tuple(min(255, c + 45) for c in base)
    dark = tuple(max(0, c - 35) for c in base)
    d.ellipse((330, -120, 760, 310), fill=light)
    d.ellipse((-160, 520, 260, 940), fill=dark)
    d.rectangle((0, 0, 26, h), fill=dark)  # spine shadow

    # Class badge
    d.rounded_rectangle((60, 60, 250, 120), radius=30, fill=(255, 255, 255))
    d.text((155, 90), f'CLASS {level}', font=_font(30), fill=base, anchor='mm')

    # Title
    title_font = _font(64)
    y = 260
    for line in _wrap(d, subject, title_font, w - 120):
        d.text((60, y), line, font=title_font, fill=(255, 255, 255))
        y += 76
    d.rectangle((60, y + 16, 180, y + 24), fill=(255, 214, 0))
    d.text((60, y + 50), book_type.upper(), font=_font(34), fill=(255, 236, 179))

    # Publisher strip
    d.rectangle((0, h - 110, w, h), fill=(255, 255, 255))
    d.text((w // 2, h - 55), publisher, font=_font(30), fill=dark, anchor='mm')

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


BANNERS = [
    ('Back to school 2026', 'Every Class 1–12 book in one place', 'Shop now', '/products', ((110, 10, 59), (204, 0, 102))),
    ('Up to 25% off', 'Guides & model tests on offer this week', 'View offers', '/products?discounted=1', ((178, 74, 10), (248, 150, 30))),
    ('SSC & HSC preparation', 'Physics, Chemistry, Biology & Higher Math', 'Explore', '/products?ordering=-created_at', ((25, 23, 26), (110, 10, 59))),
]


def make_banner(title, subtitle, colours, covers):
    """1600x500 banner artwork (gradient + fan of covers). Text is overlaid by the site from title/subtitle."""
    w, h = 1600, 500
    start, end = colours
    img = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(img)
    for x in range(w):
        t = x / w
        d.line([(x, 0), (x, h)], fill=tuple(int(start[i] + (end[i] - start[i]) * t) for i in range(3)))
    d.ellipse((1050, -260, 1800, 420), fill=tuple(min(255, c + 30) for c in end))
    for i, cover in enumerate(covers[:3]):
        thumb = Image.open(io.BytesIO(cover)).convert('RGBA').resize((220, 293))
        thumb = thumb.rotate((i - 1) * -8, expand=True, resample=Image.BICUBIC)
        img.paste(thumb, (1040 + i * 150, 70 + abs(i - 1) * 30), thumb)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=88)
    return buf.getvalue()


# Stationery department: sub-category -> sub-sub-category -> items (title, brand, price, picture, colour)
STATIONERY = [
    ('Pens & Pencils', [
        ('Ball Pens', [('Ball Pen — Blue, Pack of 10', 'Inkline', 100, 'pen', (21, 101, 192)),
                       ('Ball Pen — Black, Pack of 10', 'Inkline', 100, 'pen', (38, 38, 38))]),
        ('Gel Pens', [('Gel Pen — Assorted, Pack of 5', 'Smoothy', 150, 'pen', (106, 27, 154))]),
        ('Pencils', [('HB Pencil — Pack of 12', 'Lekhoni', 120, 'pencil', (230, 145, 20)),
                     ('2B Drawing Pencil — Pack of 6', 'Lekhoni', 90, 'pencil', (198, 40, 40))]),
    ]),
    ('Khata & Notebooks', [
        ('Khata', [('Ruled Khata — 200 pages', 'Patabahar', 80, 'notebook', (0, 131, 143)),
                   ('Math Khata, Square Grid — 120 pages', 'Patabahar', 70, 'notebook', (46, 125, 50))]),
        ('Spiral Notebooks', [('Spiral Notebook A5 — 160 pages', 'PageCraft', 140, 'spiral', (204, 0, 102))]),
    ]),
    ('Geometry & Math', [
        ('Geometry Boxes', [('Geometry Box — 9 pieces', 'Rekha', 250, 'box', (40, 53, 147))]),
        ('Calculators', [('Scientific Calculator — 240 functions', 'Gonok', 1350, 'calculator', (55, 71, 79))]),
    ]),
    ('Art & Colour', [
        ('Colour Pencils', [('Colour Pencils — 24 shades', 'Rangdhanu', 220, 'colours', (198, 40, 40))]),
        ('Crayons', [('Wax Crayons — 12 colours', 'Rangdhanu', 90, 'crayons', (245, 124, 0))]),
    ]),
    ('Bags & Bottles', [
        ('School Bags', [('School Backpack — 18 inch', 'Pathik', 1450, 'bag', (204, 0, 102))]),
        ('Water Bottles', [('Water Bottle — 600 ml', 'Pathik', 320, 'bottle', (0, 105, 92))]),
    ]),
]
RAINBOW = [(229, 57, 53), (251, 140, 0), (253, 216, 53), (67, 160, 71), (30, 136, 229), (94, 53, 177), (216, 27, 96)]


def _shade(colour, delta):
    return tuple(max(0, min(255, c + delta)) for c in colour)


def _stick(length, thickness, colour, tip, end=None):
    """A horizontal pen / pencil drawn on its own transparent layer (rotated by the caller)."""
    layer = Image.new('RGBA', (length + 40, thickness + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y0, y1 = 20, 20 + thickness
    body_end = length - 70
    if end:
        d.rounded_rectangle((20, y0, 70, y1), radius=thickness // 3, fill=end)
        d.rectangle((62, y0, 84, y1), fill=(189, 189, 189))
    d.rectangle((84 if end else 20, y0, body_end, y1), fill=colour)
    d.rectangle((84 if end else 20, y0, body_end, y0 + thickness // 4), fill=_shade(colour, 40))
    d.polygon([(body_end, y0), (body_end, y1), (length + 20, (y0 + y1) // 2)], fill=tip)
    d.polygon([(length - 10, (y0 + y1) // 2 - 7), (length - 10, (y0 + y1) // 2 + 7), (length + 20, (y0 + y1) // 2)], fill=(60, 60, 60))
    return layer


def _paste_rotated(img, layer, angle, centre):
    rotated = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(rotated, (centre[0] - rotated.width // 2, centre[1] - rotated.height // 2))


def make_stationery(kind, colour, title, brand):
    """Simple product artwork for a stationery item (600x800 PNG)."""
    w, h = 600, 800
    bg = _shade(colour, 0)
    bg = tuple(round(c * 0.12 + 255 * 0.88) for c in bg)
    img = Image.new('RGBA', (w, h), bg + (255,))
    d = ImageDraw.Draw(img)
    d.ellipse((300, -140, 760, 300), fill=tuple(round(c * 0.2 + 255 * 0.8) for c in colour) + (255,))
    d.ellipse((-180, 440, 220, 840), fill=tuple(round(c * 0.16 + 255 * 0.84) for c in colour) + (255,))
    cx, cy = 300, 330
    dark = _shade(colour, -45)

    if kind == 'pen':
        for i, off in enumerate((-70, 0, 70)):
            _paste_rotated(img, _stick(420, 34, colour if i != 1 else dark, (210, 210, 210)), 35, (cx + off, cy + off // 3))
    elif kind == 'pencil':
        for i, off in enumerate((-80, 0, 80)):
            _paste_rotated(img, _stick(420, 38, colour, (240, 205, 160), end=(244, 143, 177)), 35, (cx + off, cy + off // 3))
    elif kind == 'colours' or kind == 'crayons':
        thickness = 30 if kind == 'colours' else 44
        # Upright, slightly fanned row of pencils / crayons
        for i, c in enumerate(RAINBOW):
            k = i - 3
            layer = _stick(360 if kind == 'colours' else 260, thickness, c, (240, 205, 160) if kind == 'colours' else _shade(c, -30))
            _paste_rotated(img, layer, 90 - k * 7, (cx + k * (thickness + 12), cy + 20 + abs(k) * 12))
    elif kind in ('notebook', 'spiral'):
        d.rounded_rectangle((165, 150, 445, 520), radius=14, fill=_shade(colour, -30))
        d.rounded_rectangle((150, 135, 430, 505), radius=14, fill=colour)
        d.rounded_rectangle((200, 210, 390, 300), radius=8, fill=(255, 255, 255))
        for y in (238, 258, 278):
            d.line((215, y, 375, y), fill=_shade(colour, 60), width=3)
        if kind == 'spiral':
            for y in range(160, 500, 28):
                d.ellipse((136, y, 164, y + 16), outline=(90, 90, 90), width=4)
        else:
            d.rectangle((150, 135, 172, 505), fill=dark)
    elif kind == 'box':
        d.rounded_rectangle((120, 190, 480, 470), radius=18, fill=colour)
        d.rounded_rectangle((120, 190, 480, 250), radius=18, fill=dark)
        d.pieslice((200, 280, 400, 480), 180, 360, fill=(255, 255, 255))
        d.pieslice((235, 315, 365, 445), 180, 360, fill=colour)
        d.rectangle((150, 395, 450, 425), fill=(255, 236, 179))
        for x in range(160, 445, 18):
            d.line((x, 395, x, 405 if (x // 18) % 2 else 412), fill=(120, 90, 40), width=2)
    elif kind == 'calculator':
        d.rounded_rectangle((170, 120, 430, 540), radius=26, fill=colour)
        d.rounded_rectangle((200, 155, 400, 235), radius=8, fill=(200, 230, 201))
        d.text((385, 195), '3.1416', font=_font(34), fill=(40, 60, 40), anchor='rm')
        for r in range(5):
            for c in range(4):
                x, y = 200 + c * 52, 260 + r * 54
                key = (255, 112, 67) if (r, c) == (4, 3) else (236, 239, 241)
                d.rounded_rectangle((x, y, x + 40, y + 40), radius=8, fill=key)
    elif kind == 'bag':
        d.arc((235, 90, 365, 200), 180, 360, fill=dark, width=18)
        d.rounded_rectangle((150, 150, 450, 540), radius=60, fill=colour)
        d.rounded_rectangle((195, 330, 405, 500), radius=30, fill=dark)
        d.line((215, 360, 385, 360), fill=(255, 214, 0), width=6)
        d.rectangle((285, 170, 315, 320), fill=_shade(colour, 35))
    elif kind == 'bottle':
        d.rounded_rectangle((250, 105, 350, 165), radius=12, fill=dark)
        d.rounded_rectangle((215, 150, 385, 540), radius=50, fill=colour)
        d.rectangle((215, 300, 385, 400), fill=(255, 255, 255))
        d.text((300, 350), brand.upper(), font=_font(30), fill=colour, anchor='mm')
        d.rounded_rectangle((235, 180, 255, 280), radius=10, fill=_shade(colour, 50))

    # Name strip
    d.rectangle((0, h - 190, w, h), fill=(255, 255, 255, 255))
    lines = _wrap(d, title, _font(32), w - 80)[:2]
    y = h - 170
    for line in lines:
        d.text((40, y), line, font=_font(32), fill=(25, 23, 26))
        y += 42
    d.text((40, h - 52), brand.upper(), font=_font(24), fill=dark)

    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='PNG', optimize=True)
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Seed a school book catalogue: Class 1-12, subjects, sample books with covers.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Remove non-book categories and hide products outside the class tree.')

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)
        shops = self._sellers()

        class_ids = []
        created = 0
        for level in range(1, 13):
            klass, _ = Category.objects.get_or_create(name=f'Class {level}', parent=None)
            klass.position = level
            klass.description = BANGLA_CLASS[level - 1]
            klass.save()
            class_ids.append(klass.id)

            for pos, subject in enumerate(subjects_for(level), start=1):
                sub, _ = Category.objects.get_or_create(name=subject, parent=klass)
                if sub.position != pos:
                    sub.position = pos
                    sub.save(update_fields=['position'])

                types = BOOK_TYPES if level >= 6 else BOOK_TYPES[:2]
                for book_type, (lo, hi), blurb in types:
                    publisher = rng.choice(PUBLISHERS)
                    author = rng.choice(AUTHORS)
                    shop = shops[(level + pos) % len(shops)]
                    price = Decimal(rng.randrange(lo, hi, 10))
                    discount = rng.choice([0, 0, 10, 15, 20, 25])
                    title = f'{subject} {book_type} — Class {level}'
                    product, is_new = Product.objects.get_or_create(
                        shop=shop, title=title,
                        defaults={
                            'category': sub, 'author': author, 'publisher': publisher, 'price': price,
                            'stock_quantity': rng.choice([0, 3, 12, 25, 40, 60]), 'low_stock_threshold': 5, 'moq': 1,
                            'discount_type': 'PERCENTAGE' if discount else 'NONE',
                            'discount_value': Decimal(discount) if discount else None,
                            'woner_commission': Decimal(rng.choice([5, 8, 10])),
                            'approval_status': 'APPROVED', 'is_active': True,
                            'description': f'{subject} {book_type.lower()} for Class {level} ({BANGLA_CLASS[level - 1]}). {blurb} '
                                           f'Written by {author}, published by {publisher}.',
                        },
                    )
                    created += int(is_new)
                    if not product.images.exists():
                        ProductImage.objects.create(
                            product=product, is_primary=True,
                            image=ContentFile(make_cover(subject, level, book_type, publisher), name=f'book-{product.id}.png'),
                        )

        stationery, stationery_new = self._stationery(shops[0], rng)
        self._marketing(class_ids)

        if options['reset']:
            keep_roots = class_ids + [stationery.id]
            removed, _ = Category.objects.filter(parent__isnull=True).exclude(id__in=keep_roots).delete()
            hidden = (Product.objects.filter(is_active=True)
                      .exclude(category_id__in=Category.family_ids(keep_roots))
                      .update(is_active=False))
            self.stdout.write(f'Reset: removed {removed} non-book category rows, hid {hidden} non-book products.')

        self.stdout.write(self.style.SUCCESS(
            f'Book catalogue ready: 12 classes, {Category.objects.filter(parent_id__in=class_ids).count()} subjects, '
            f'{created} new books, {stationery_new} new stationery items. Seller logins: 01744444444 / 01755555555 (password 12345678).'
        ))

    def _stationery(self, shop, rng):
        """Stationery department, three levels deep: Stationery -> Pens & Pencils -> Ball Pens -> items."""
        root, _ = Category.objects.get_or_create(name='Stationery', parent=None)
        root.position = 100
        root.description = 'খাতা, কলম ও স্কুলের প্রয়োজনীয় সব জিনিস'
        root.save()
        created = 0
        for pos, (group, types) in enumerate(STATIONERY, start=1):
            sub, _ = Category.objects.get_or_create(name=group, parent=root)
            Category.objects.filter(pk=sub.pk).update(position=pos)
            for tpos, (type_name, items) in enumerate(types, start=1):
                leaf, _ = Category.objects.get_or_create(name=type_name, parent=sub)
                Category.objects.filter(pk=leaf.pk).update(position=tpos)
                for title, brand, price, kind, colour in items:
                    discount = rng.choice([0, 0, 10, 15])
                    product, is_new = Product.objects.get_or_create(
                        shop=shop, title=title,
                        defaults={
                            'category': leaf, 'publisher': brand, 'price': Decimal(price),
                            'stock_quantity': rng.choice([15, 30, 50, 80]), 'low_stock_threshold': 5, 'moq': 1,
                            'discount_type': 'PERCENTAGE' if discount else 'NONE',
                            'discount_value': Decimal(discount) if discount else None,
                            'woner_commission': Decimal(0), 'approval_status': 'APPROVED', 'is_active': True,
                            'description': f'{title} by {brand}. Good quality {type_name.lower()} for school and home — '
                                           f'part of our {group.lower()} range.',
                        },
                    )
                    created += int(is_new)
                    if not product.images.exists():
                        ProductImage.objects.create(
                            product=product, is_primary=True,
                            image=ContentFile(make_stationery(kind, colour, title, brand), name=f'stationery-{product.id}.png'),
                        )
        return root, created

    def _sellers(self):
        role, _ = Lookup.objects.get_or_create(name='ROLE', value='RETAILER', defaults={'is_active': True})
        group, _ = Group.objects.get_or_create(name='retailer')
        shops = []
        for spec in SELLERS:
            user, is_new = User.objects.get_or_create(
                phone_number=spec['phone'],
                defaults={'full_name': spec['name'], 'role': role, 'is_approved': True, 'is_phone_verified': True},
            )
            if is_new:
                user.set_password('12345678')
                user.save()
            user.groups.add(group)
            KYCProfile.objects.get_or_create(user=user, defaults={'status': 'APPROVED', 'nid_number': '1990000000' + spec['phone'][-3:]})
            Wallet.objects.get_or_create(user=user)
            city, _ = City.objects.get_or_create(name=spec['city'])
            shop, _ = ShopProfile.objects.get_or_create(
                user=user,
                defaults={'shop_name': spec['name'], 'shop_type': 'RETAILER', 'city': city,
                          'shop_address': spec['address'], 'description': spec['description']},
            )
            shops.append(shop)
        return shops

    def _marketing(self, class_ids):
        if not Banner.objects.exists():
            for pos, (title, subtitle, cta, link, colours) in enumerate(BANNERS):
                covers = [make_cover(subj, 9, 'Guide', PUBLISHERS[i]) for i, subj in enumerate(['Physics', 'Mathematics', 'English'])]
                Banner.objects.create(
                    title=title, subtitle=subtitle, button_text=cta, link_url=link, position=pos,
                    image=ContentFile(make_banner(title, subtitle, colours, covers), name=f'banner-{pos + 1}.jpg'),
                )
        Coupon.objects.get_or_create(code='WELCOME10', defaults={
            'description': '10% off your first book order (max ৳150)', 'discount_type': 'PERCENTAGE',
            'value': Decimal('10'), 'max_discount': Decimal('150'), 'min_order_amount': Decimal('300'),
        })
        page, created = LandingPage.objects.get_or_create(slug='ssc-science-pack', defaults={
            'title': 'SSC Science Pack — Class 9 & 10',
            'headline': 'Physics, Chemistry, Biology & Higher Math — order the full set in one go',
            'description': 'Everything an SSC science student needs for the year. Pick the books you want, tell us where to deliver, '
                           'and pay cash on delivery. Our team will call you to confirm the order.',
            'cta_text': 'Order the pack',
        })
        if created:
            books = (Product.objects.filter(category__parent__name__in=['Class 9', 'Class 10'], is_active=True,
                                            category__name__in=['Physics', 'Chemistry', 'Biology', 'Higher Mathematics'],
                                            title__contains='Guide').order_by('category__parent__position', 'category__position'))
            for pos, book in enumerate(books[:8]):
                LandingPageItem.objects.create(landing_page=page, product=book, position=pos, is_preselected=pos < 4)

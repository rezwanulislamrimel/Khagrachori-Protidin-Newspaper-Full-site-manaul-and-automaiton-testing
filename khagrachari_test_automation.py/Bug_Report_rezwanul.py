# full_site_automation.py
import time
import traceback
import requests
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, WebDriverException
import pandas as pd
import platform
import math
import json

# -----------------------
# Configuration
# -----------------------
TARGET_URL = "https://khagracharipratidin.com/"   # change if needed
OUTPUT_FILE = "Automation_Bug_Report.xlsx"
TIMEOUT = 3
# Breakpoints to test responsiveness
DESKTOP_SIZE = (1366, 768)
MOBILE_SIZE = (390, 844)  # iPhone 14-ish
VIEWPORTS = [DESKTOP_SIZE, MOBILE_SIZE]

# Map of checks to severity (you can tune)
SEVERITY_MAP = {
    "header_overlap": "High",
    "color_consistency": "Medium",
    "text_contrast": "High",
    "spacing": "Low",
    "typography_hierarchy": "Medium",
    "responsive_break": "High",
    "broken_links": "High",
    "missing_thumbnails": "Medium",
    "embedded_images": "Medium",
    "search_not_working": "High",
    "social_links": "Medium",
    "read_more_issue": "High",
    "pagination_issue": "Medium",
    "menu_collapse": "High",
    "image_resize_mobile": "Medium",
    "horizontal_scroll": "High",
    "footer_stack": "Low",
    "font_size_mobile": "Medium",
    "homepage_load": "High",
    "unoptimized_images": "Medium",
    "placeholder_text": "Medium",
    "twitter_redirect": "Medium",
    "console_errors": "High",
    "js_blocking": "Medium",
    "text_overlap_mobile": "High"
}

# -----------------------
# Helpers
# -----------------------
def add_row(rows, bug_id, title, severity, steps, expected, actual, status="New", screenshot=None, environment=None):
    rows.append({
        "Bug ID": bug_id,
        "Bug Title": title,
        "Severity": severity,
        "Steps to Reproduce": steps,
        "Expected Result": expected,
        "Actual Result": actual,
        "Screenshot": screenshot or "",
        "Status": status,
        "Environment": environment or ""
    })

def safe_js(driver, script):
    try:
        return driver.execute_script(script)
    except Exception:
        return None

def compute_luminance(rgb):
    # rgb: tuple of ints (r,g,b) 0..255
    def channel(c):
        c = c/255.0
        return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    r,g,b = rgb
    return 0.2126*channel(r) + 0.7152*channel(g) + 0.0722*channel(b)

def hex_to_rgb(hexcol):
    hexcol = hexcol.strip()
    if hexcol.startswith("rgb"):
        nums = [int(x) for x in hexcol.replace("rgba","").replace("rgb","").replace("(","").replace(")","").split(",")[:3]]
        return tuple(nums)
    if hexcol.startswith("#"):
        hexcol = hexcol[1:]
    if len(hexcol) == 3:
        hexcol = ''.join([c*2 for c in hexcol])
    return tuple(int(hexcol[i:i+2], 16) for i in (0, 2, 4))

# -----------------------
# Setup WebDriver
# -----------------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# Enable browser console logs
options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
# headless? comment out if you want to see browser
# options.add_argument("--headless=new")
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
driver.set_page_load_timeout(30)

rows = []
start_time_script = time.time()

# -----------------------
# Visit homepage & baseline
# -----------------------
try:
    t0 = time.time()
    driver.get(TARGET_URL)
    time.sleep(2)
    load_time = safe_js(driver, "return window.performance.timing.loadEventEnd - window.performance.timing.navigationStart;") or (time.time() - t0)*1000
    # convert to seconds
    homepage_load_seconds = load_time/1000.0 if isinstance(load_time, (int, float)) else float(load_time)
except Exception as e:
    homepage_load_seconds = None
    print("Error loading homepage:", e)

# -----------------------
# Test implementations (25 checks)
# -----------------------

# 1 Header overlap (desktop)
try:
    driver.set_window_size(*DESKTOP_SIZE)
    time.sleep(0.8)
    steps = "1. Open homepage in desktop resolution (1366x768).\n2. Inspect header and logo positions."
    expected = "Header and menu aligned properly without overlapping the logo."
    try:
        header = driver.find_element(By.TAG_NAME, "header")
        logo = None
        # heuristics to find logo
        for cls in ["logo", "site-logo", "navbar-brand", "brand"]:
            try:
                logo = driver.find_element(By.CLASS_NAME, cls); break
            except:
                logo = None
        if not logo:
            # fallback: find img in header
            imgs = header.find_elements(By.TAG_NAME, "img")
            logo = imgs[0] if imgs else None
        if header and logo:
            header_box = header.rect
            logo_box = logo.rect
            # if menu x overlaps logo x (rough guess)
            if abs((logo_box['x']+logo_box['width']) - (header_box['x'] + header_box['width'])) < 0: # fallback not meaningful
                # use positional check: if logo right edge > header right edge (rare) -> overlap
                pass
            # more practical: detect if any element near logo overlaps by bounding boxes
            # we check a few menu items
            maybe_overlap = False
            try:
                menu = driver.find_element(By.CSS_SELECTOR, "nav, .nav, .navbar, #main-nav")
                menu_box = menu.rect
                if menu_box['x'] < (logo_box['x'] + logo_box['width']):
                    maybe_overlap = True
            except:
                # fallback: scan header children bounding boxes
                children = header.find_elements(By.XPATH, "./*")
                for ch in children:
                    r = ch.rect
                    if r['x'] < (logo_box['x'] + logo_box['width']) and r['y'] <= logo_box['y']+logo_box['height']:
                        if ch.tag_name.lower() != 'img':
                            maybe_overlap = True
                            break
            if maybe_overlap:
                actual = "Menu overlaps logo on desktop header in tested viewport."
                add_row(rows, "001", "Header overlaps logo on desktop", SEVERITY_MAP["header_overlap"], steps, expected, actual, screenshot="001_HeaderOverlap.png", environment=f"Chrome, {DESKTOP_SIZE[0]}x{DESKTOP_SIZE[1]}")
            else:
                # pass - still include as informational (no bug)
                pass
        else:
            # can't find header/logo -> report as possible issue
            add_row(rows, "001", "Header or logo element not found", SEVERITY_MAP["header_overlap"], steps, expected, "Header or logo element couldn't be detected; manual check needed", screenshot=None)
    except Exception as e:
        add_row(rows, "001", "Header overlap check error", SEVERITY_MAP["header_overlap"], steps, expected, f"Error during check: {e}")
except Exception as e:
    add_row(rows, "001", "Header overlap script crashed", SEVERITY_MAP["header_overlap"], "Open homepage", "Header aligns", f"Exception: {e}")

# 2 Color consistency (basic color check)
try:
    steps = "1. Visit homepage and article pages; 2. Collect colors for primary buttons and links."
    expected = "All buttons and primary links use the brand color (consistent)."
    # grab colors for first few buttons and anchor links
    btn_colors = safe_js(driver, """
    var out=[];
    var btns = document.querySelectorAll('button, a.button, a.btn, .btn');
    for (var i=0;i<Math.min(btns.length,8);i++){
        out.push(window.getComputedStyle(btns[i]).getPropertyValue('background-color') || window.getComputedStyle(btns[i]).getPropertyValue('color'));
    }
    return out;
    """) or []
    link_colors = safe_js(driver, """
    var links=document.querySelectorAll('a');
    var out=[];
    for(var i=0;i<Math.min(10,links.length);i++){ out.push(window.getComputedStyle(links[i]).getPropertyValue('color')); }
    return out;
    """) or []
    # normalize and compare unique
    uniq = list(set(btn_colors + link_colors))
    if len(uniq) > 2:
        actual = f"Multiple primary colors detected: {uniq[:6]}"
        add_row(rows, "002", "Inconsistent color scheme across UI", SEVERITY_MAP["color_consistency"], steps, expected, actual, screenshot="002_ColorMismatch.png")
except Exception as e:
    add_row(rows, "002", "Color consistency check error", SEVERITY_MAP["color_consistency"], steps, expected, f"Error: {e}")

# 3 Text contrast (WCAG AA simple check)
try:
    steps = "1. Inspect text color and background for main article paragraphs."
    expected = "Text must be readable with sufficient contrast (WCAG AA roughly)."
    # pick some paragraphs
    paras = driver.find_elements(By.TAG_NAME, "p")[:8]
    contrast_issues = []
    for p in paras:
        color = safe_js(driver, "return window.getComputedStyle(arguments[0]).getPropertyValue('color');", )
    # use JS to compute a list of color pairs (fg/bg)
    color_pairs = safe_js(driver, """
    var out=[];
    var paras = document.querySelectorAll('p');
    for(var i=0;i<Math.min(10,paras.length);i++){
        var fg = window.getComputedStyle(paras[i]).getPropertyValue('color');
        var bgel = paras[i];
        // find effective background by walking up parents
        var bg = '';
        var el = paras[i];
        while(el && el.nodeName.toLowerCase()!='html'){
            var b = window.getComputedStyle(el).getPropertyValue('background-color');
            if(b && b!='rgba(0, 0, 0, 0)' && b!='transparent'){ bg = b; break; }
            el = el.parentElement;
        }
        if(!bg) bg = window.getComputedStyle(document.body).getPropertyValue('background-color') || 'rgb(255,255,255)';
        out.push([fg,bg]);
    }
    return out;
    """) or []
    def contrast_ratio(fg, bg):
        try:
            fr = hex_to_rgb(fg)
            br = hex_to_rgb(bg)
            l1 = compute_luminance(fr)
            l2 = compute_luminance(br)
            L1 = max(l1, l2)
            L2 = min(l1, l2)
            return (L1 + 0.05) / (L2 + 0.05)
        except:
            return None
    low_contrast = []
    for fg,bg in color_pairs:
        cr = contrast_ratio(fg, bg)
        if cr is not None and cr < 4.5:  # WCAG AA for normal text
            low_contrast.append((fg,bg,cr))
    if low_contrast:
        actual = f"Found low contrast pairs (fg,bg,ratio): {[(x[0],x[1],round(x[2],2)) for x in low_contrast[:5]]}"
        add_row(rows, "003", "Poor text contrast on light background", SEVERITY_MAP["text_contrast"], steps, expected, actual, screenshot="003_TextContrast.png")
except Exception as e:
    add_row(rows, "003", "Text contrast check error", SEVERITY_MAP["text_contrast"], steps, expected, f"Error: {e}")

# 4 Uneven spacing between sections (heuristic)
try:
    steps = "1. Scroll through homepage, measure vertical gaps between direct children of main content."
    expected = "Consistent spacing between sections"
    # gather y coordinates of top-level sections
    sections = safe_js(driver, """
    var out=[];
    var main = document.querySelector('main') || document.body;
    var children = main.children;
    for(var i=0;i<children.length;i++){
        var r = children[i].getBoundingClientRect();
        out.push({tag: children[i].tagName, y: r.top, h: r.height});
    }
    return out.slice(0,12);
    """) or []
    gaps = []
    for i in range(1, len(sections)):
        prev = sections[i-1]
        cur = sections[i]
        gap = cur['y'] - (prev['y'] + prev['h'])
        gaps.append(gap)
    if gaps:
        avg = sum(gaps)/len(gaps)
        # if many gaps deviate > 2x avg, report
        big_devs = [g for g in gaps if abs(g - avg) > (avg * 1.5 + 5)]
        if big_devs:
            actual = f"Uneven gaps detected between sections, sample gaps: {gaps[:6]}"
            add_row(rows, "004", "Uneven spacing between sections", SEVERITY_MAP["spacing"], steps, expected, actual, screenshot="004_SectionSpacing.png")
except Exception as e:
    add_row(rows, "004", "Spacing check error", SEVERITY_MAP["spacing"], steps, "Consistent spacing", f"Error: {e}")

# 5 Typography hierarchy (simple font-size check)
try:
    steps = "1. Inspect H1/H2 and paragraph sizes on article pages."
    expected = "H1 > H2 > body sizes to maintain hierarchy"
    sizes = safe_js(driver, """
    var out={h1:[],h2:[],p:[]};
    var h1s = document.getElementsByTagName('h1');
    for(var i=0;i<h1s.length;i++) out.h1.push(window.getComputedStyle(h1s[i]).getPropertyValue('font-size'));
    var h2s = document.getElementsByTagName('h2');
    for(var i=0;i<h2s.length;i++) out.h2.push(window.getComputedStyle(h2s[i]).getPropertyValue('font-size'));
    var ps = document.getElementsByTagName('p');
    for(var i=0;i<Math.min(8,ps.length);i++) out.p.push(window.getComputedStyle(ps[i]).getPropertyValue('font-size'));
    return out;
    """) or {}
    # convert to numeric px
    def px_to_float(s):
        try:
            return float(s.replace("px","").strip())
        except:
            return None
    h1 = [px_to_float(x) for x in sizes.get("h1",[])]
    h2 = [px_to_float(x) for x in sizes.get("h2",[])]
    p = [px_to_float(x) for x in sizes.get("p",[])]
    if h1 and h2:
        if (sum(h1)/len(h1)) <= (sum(h2)/len(h2)):
            add_row(rows, "005", "Incorrect typography hierarchy", SEVERITY_MAP["typography_hierarchy"], steps, expected, "H1 sizes are not larger than H2 sizes", screenshot="005_Typography.png")
except Exception as e:
    add_row(rows, "005", "Typography check error", SEVERITY_MAP["typography_hierarchy"], steps, expected, f"Error: {e}")

# 6 Responsive layout breaks (mobile)
try:
    steps = "1. Open site on mobile viewport (390x844) and inspect major layout sections."
    expected = "Layout should adapt correctly to small screens."
    driver.set_window_size(*MOBILE_SIZE)
    time.sleep(1.2)
    # check if any element wider than viewport exists
    inner_w = safe_js(driver, "return window.innerWidth;")
    max_width = safe_js(driver, "return Math.max.apply(null, Array.prototype.slice.call(document.querySelectorAll('body, body *')).map(function(n){return n.getBoundingClientRect().width;})));")
    if max_width and inner_w and max_width > inner_w + 5:
        add_row(rows, "006", "Responsive layout breaks on mobile", SEVERITY_MAP["responsive_break"], steps, expected, f"A child element width {max_width}px exceeds viewport width {inner_w}px", screenshot="006_Responsive.png", environment=f"Mobile {MOBILE_SIZE[0]}x{MOBILE_SIZE[1]}")
except Exception as e:
    add_row(rows, "006", "Responsive check error", SEVERITY_MAP["responsive_break"], steps, expected, f"Error: {e}")

# 7 Broken navigation links (HTTP status or redirects)
try:
    steps = "1. Collect links from main nav and article lists and check HTTP status codes via requests."
    expected = "All internal links should return 200/valid responses."
    anchors = driver.find_elements(By.TAG_NAME, "a")
    checked = 0
    broken = []
    for a in anchors[:120]:  # limit to top 120 links
        href = a.get_attribute("href")
        if not href or not href.startswith("http"):
            continue
        checked += 1
        try:
            r = requests.head(href, timeout=5, allow_redirects=True)
            status = r.status_code
            if status >= 400:
                broken.append((href, status))
        except Exception as e:
            broken.append((href, str(e)))
    if broken:
        actual = f"Found broken or error links sample: {broken[:6]}"
        add_row(rows, "007", "Broken navigation links", SEVERITY_MAP["broken_links"], steps, expected, actual, screenshot="007_BrokenLinks.png")
except Exception as e:
    add_row(rows, "007", "Broken links check error", SEVERITY_MAP["broken_links"], steps, expected, f"Error: {e}")

# 8 Missing article thumbnails
try:
    steps = "1. Inspect article list thumbnails on homepage and article list pages."
    expected = "Thumbnails should display with valid src."
    imgs = driver.find_elements(By.CSS_SELECTOR, "img")
    missing = []
    for img in imgs[:120]:
        src = img.get_attribute("src")
        if not src:
            missing.append("empty-src")
            continue
        # quick HEAD check
        try:
            r = requests.head(src, timeout=5)
            if r.status_code >= 400:
                missing.append((src, r.status_code))
        except:
            # try GET
            try:
                r = requests.get(src, timeout=5)
                if r.status_code >= 400:
                    missing.append((src, r.status_code))
            except Exception as e:
                missing.append((src, str(e)))
    if missing:
        add_row(rows, "008", "Missing article thumbnails", SEVERITY_MAP["missing_thumbnails"], steps, expected, f"Missing/broken thumbnails sample: {missing[:6]}", screenshot="008_Thumbnails.png")
except Exception as e:
    add_row(rows, "008", "Thumbnail check error", SEVERITY_MAP["missing_thumbnails"], steps, expected, f"Error: {e}")

# 9 Embedded images not loading (image naturalWidth check via JS)
try:
    steps = "1. Open a few articles and check if images loaded (naturalWidth > 0)."
    expected = "Images must load fully (naturalWidth>0)."
    imgs_info = safe_js(driver, """
    var out=[];
    var imgs = document.querySelectorAll('img');
    for(var i=0;i<Math.min(60, imgs.length); i++){
        out.push({src: imgs[i].src, nw: imgs[i].naturalWidth});
    }
    return out;
    """) or []
    missing = [i for i in imgs_info if not i['nw']]
    if missing:
        add_row(rows, "009", "Embedded images not loading", SEVERITY_MAP["embedded_images"], steps, expected, f"Images with naturalWidth=0 sample: {missing[:6]}", screenshot="009_ImagesMissing.png")
except Exception as e:
    add_row(rows, "009", "Embedded image check error", SEVERITY_MAP["embedded_images"], steps, expected, f"Error: {e}")

# 10 Spelling/grammar in headlines (basic: check for placeholder text or obvious tokens)
try:
    steps = "1. Scan headlines for common typos or placeholder tokens."
    expected = "No spelling/grammar errors in headlines."
    headings = driver.find_elements(By.XPATH, "//h1|//h2|//h3")
    typos = []
    placeholders = ["INSERT", "TODO", "TBD"]
    for h in headings[:60]:
        text = h.text.strip()
        for p in placeholders:
            if p in text.upper():
                typos.append((text, p))
    if typos:
        add_row(rows, "010", "Spelling/placeholder found in headlines", SEVERITY_MAP["text_overlap_mobile"], steps, expected, f"Found placeholders in headings: {typos[:6]}", screenshot="010_Grammar.png")
except Exception as e:
    add_row(rows, "010", "Headline grammar check error", "Low", steps, expected, f"Error: {e}")

# 11 Search button not working (functional)
try:
    steps = "1. Enter a common keyword into search field and click search button."
    expected = "Search returns relevant results or redirects to search results page."
    # try to find input + button
    search_input = None
    search_btn = None
    try:
        search_input = driver.find_element(By.CSS_SELECTOR, "input[type='search'], input[aria-label*='search'], input[name='q'], input[name='s']")
    except:
        pass
    try:
        search_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button.search, .search-button")
    except:
        # try by text 'search'
        elems = driver.find_elements(By.TAG_NAME, "button")
        for e in elems:
            if 'search' in e.text.lower():
                search_btn = e
                break
    if search_input and search_btn:
        try:
            search_input.clear()
            search_input.send_keys("test")
            search_btn.click()
            time.sleep(2)
            # if results container exists or url changed we consider pass
            if "search" not in driver.current_url.lower() and not driver.find_elements(By.CSS_SELECTOR, ".search-results, .results, #search"):
                add_row(rows, "011", "Search button not working", SEVERITY_MAP["search_not_working"], steps, expected, "Search action did not produce results or navigate to results page", screenshot="011_SearchButton.png")
        except Exception as e:
            add_row(rows, "011", "Search button error", SEVERITY_MAP["search_not_working"], steps, expected, f"Error interacting with search: {e}")
    else:
        add_row(rows, "011", "Search elements not found", SEVERITY_MAP["search_not_working"], steps, expected, "Search input/button not detected on page")
except Exception as e:
    add_row(rows, "011", "Search check error", SEVERITY_MAP["search_not_working"], steps, expected, f"Error: {e}")

# 12 Incorrect social media links (check hrefs)
try:
    steps = "1. Click/view social icons in header/footer and check href target domains."
    expected = "Social icons link to correct official pages."
    social_selectors = ["a[href*='facebook.com']", "a[href*='twitter.com']", "a[href*='x.com']", "a[href*='instagram.com']", "a[href*='linkedin.com']"]
    bad = []
    for sel in social_selectors:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        for e in elems:
            href = e.get_attribute("href")
            if href and ("example.com" in href or href.endswith("#") or "mailto:" in href):
                bad.append(href)
    if bad:
        add_row(rows, "012", "Incorrect social media links", SEVERITY_MAP["social_links"], steps, expected, f"Invalid or placeholder social links: {bad[:6]}", screenshot="012_SocialLinks.png")
except Exception as e:
    add_row(rows, "012", "Social link check error", SEVERITY_MAP["social_links"], steps, expected, f"Error: {e}")

# 13 Read More button navigation issue (check first news cards)
try:
    steps = "1. Click 'Read More' on news cards and confirm full article opens."
    expected = "Read More navigates to full article page."
    read_more_elems = driver.find_elements(By.XPATH, "//a[contains(text(), 'Read More') or contains(text(), 'Read more') or contains(@class,'read-more')]")
    inconsistent = False
    for a in read_more_elems[:8]:
        href = a.get_attribute("href")
        if not href:
            inconsistent = True
            break
        # quick HEAD check
        try:
            r = requests.head(href, timeout=5)
            if r.status_code >= 400:
                inconsistent = True
                break
        except:
            inconsistent = True
            break
    if inconsistent:
        add_row(rows, "013", "Read More button navigation issue", SEVERITY_MAP["read_more_issue"], steps, expected, "Some 'Read More' links are missing href or return error", screenshot="013_ReadMore.png")
except Exception as e:
    add_row(rows, "013", "Read more check error", SEVERITY_MAP["read_more_issue"], steps, expected, f"Error: {e}")

# 14 Pagination buttons behavior
try:
    steps = "1. Use pagination Next/Prev on article lists and check behavior at first/last pages."
    expected = "Pagination should hide/disable 'Next' on last page."
    # heuristic: find 'next' or 'older' buttons
    pag_next = None
    try:
        pag_next = driver.find_element(By.CSS_SELECTOR, "a[rel='next'], .next, .pagination .next, a[aria-label='next']")
    except:
        pass
    # try clicking until last page detection (limit)
    if pag_next:
        try:
            hrefs = []
            for _ in range(6):
                href = driver.current_url
                hrefs.append(href)
                # if next disabled or not clickable break
                try:
                    if not pag_next.is_enabled():
                        break
                    pag_next.click()
                    time.sleep(1.2)
                    # find next again
                    pag_next = driver.find_element(By.CSS_SELECTOR, "a[rel='next'], .next, .pagination .next, a[aria-label='next']")
                except Exception:
                    break
            # if loop ended but next still visible on final page -> bug
            # simple detection: check if current page shows next still
            try:
                next_visible = driver.find_element(By.CSS_SELECTOR, "a[rel='next'], .next, .pagination .next, a[aria-label='next']")
                # if still visible and not disabled, flag
                if next_visible and next_visible.is_displayed() and next_visible.is_enabled():
                    add_row(rows, "014", "Pagination Next button visible on last page", SEVERITY_MAP["pagination_issue"], steps, expected, "Next button remains visible/enabled on last page", screenshot="014_Pagination.png")
            except:
                pass
            # navigate back to homepage
            driver.get(TARGET_URL)
            time.sleep(1.0)
        except Exception:
            pass
    else:
        # If no pagination found, pass or ignore
        pass
except Exception as e:
    add_row(rows, "014", "Pagination check error", SEVERITY_MAP["pagination_issue"], steps, expected, f"Error: {e}")

# 15 Header menu not collapsing on mobile
try:
    steps = "1. Open site on mobile viewport (390x844) and open the header/menu."
    expected = "Header should collapse to a hamburger menu on mobile."
    driver.set_window_size(*MOBILE_SIZE)
    time.sleep(1.0)
    # detect if there's a hamburger button
    try:
        hamb = driver.find_element(By.CSS_SELECTOR, ".hamburger, .menu-toggle, .navbar-toggler, button[aria-expanded]")
        # click and observe overlay or collapse
        hamb.click()
        time.sleep(0.8)
    except:
        # if we find nav still visible and full-size -> bug
        navs = driver.find_elements(By.TAG_NAME, "nav")
        for n in navs[:2]:
            r = n.rect
            if r and r['width'] and r['width'] > MOBILE_SIZE[0]*0.8:
                add_row(rows, "015", "Header menu not collapsing on mobile", SEVERITY_MAP["menu_collapse"], steps, expected, "Menu remains full-size and overlaps content on mobile", screenshot="015_HeaderMenu.png")
                break
except Exception as e:
    add_row(rows, "015", "Header menu mobile check error", SEVERITY_MAP["menu_collapse"], steps, expected, f"Error: {e}")

# 16 Images not resizing on mobile (large images)
try:
    steps = "1. Open image-rich pages on mobile and observe image widths relative to viewport."
    expected = "Images scale to fit screen width."
    driver.set_window_size(*MOBILE_SIZE)
    time.sleep(1.0)
    imgs = driver.find_elements(By.TAG_NAME, "img")
    oversized = []
    for img in imgs[:60]:
        try:
            rect = img.rect
            if rect and rect['width'] > MOBILE_SIZE[0] + 5:
                oversized.append((img.get_attribute("src") or "", rect['width']))
        except:
            continue
    if oversized:
        add_row(rows, "016", "Images not resizing on mobile", SEVERITY_MAP["image_resize_mobile"], steps, expected, f"Images exceeding viewport width sample: {oversized[:6]}", screenshot="016_ImageResize.png")
except Exception as e:
    add_row(rows, "016", "Image resize mobile check error", SEVERITY_MAP["image_resize_mobile"], steps, expected, f"Error: {e}")

# 17 Horizontal scrolling required on mobile (document width > innerWidth)
try:
    steps = "1. On mobile viewport, check if body scroll width exceeds innerWidth."
    expected = "No horizontal scrolling required."
    driver.set_window_size(*MOBILE_SIZE)
    time.sleep(0.6)
    inner_w = safe_js(driver, "return window.innerWidth;")
    body_w = safe_js(driver, "return document.body.scrollWidth || document.documentElement.scrollWidth;")
    if body_w and inner_w and body_w > inner_w + 5:
        add_row(rows, "017", "Horizontal scrolling required on mobile", SEVERITY_MAP["horizontal_scroll"], steps, expected, f"Page scrollWidth {body_w}px > viewport {inner_w}px", screenshot="017_HorizontalScroll.png")
except Exception as e:
    add_row(rows, "017", "Horizontal scroll check error", SEVERITY_MAP["horizontal_scroll"], steps, expected, f"Error: {e}")

# 18 Console errors logged
try:
    steps = "1. Open DevTools console logs and check for JS errors."
    expected = "No JavaScript console errors."
    logs = driver.get_log("browser")
    error_logs = [l for l in logs if l['level'] == 'SEVERE' or 'error' in l['message'].lower()]
    if error_logs:
        sample = [(e['level'], e['message'][:160]) for e in error_logs[:6]]
        add_row(rows, "018", "Console errors logged", SEVERITY_MAP["console_errors"], steps, expected, f"Console errors sample: {sample}", screenshot="018_ConsoleErrors.png")
except Exception as e:
    add_row(rows, "018", "Console log check error", SEVERITY_MAP["console_errors"], steps, expected, f"Error: {e}")

# 19 JS blocking main-thread rendering (measure long tasks)
try:
    steps = "1. Use performance entries to check long tasks/main-thread blocking."
    expected = "No long main-thread blocking scripts delaying initial load."
    perf = safe_js(driver, "return window.performance.getEntriesByType('longtask').map(e=>({name:e.name, start:e.startTime, dur:e.duration}));")
    if perf and len(perf) > 0:
        long_tasks = [p for p in perf if p.get('dur',0) > 50]  # ms > 50 is meaningful
        if long_tasks:
            add_row(rows, "019", "JS blocking main-thread rendering", SEVERITY_MAP["js_blocking"], steps, expected, f"Long tasks found sample: {long_tasks[:6]}", screenshot="019_JSBlocking.png")
except Exception as e:
    # fallback: measure nav timing loadEventEnd - domContentLoaded
    try:
        nav = safe_js(driver, "return window.performance.timing")
        if nav:
            d = nav.get('loadEventEnd',0) - nav.get('navigationStart',0)
            if d and d > 3000:
                add_row(rows, "019", "JS blocking suspected", SEVERITY_MAP["js_blocking"], steps, expected, f"Page load time ~{d}ms suggests blocking scripts", screenshot="019_JSBlocking.png")
    except Exception as ex:
        add_row(rows, "019", "JS blocking check error", SEVERITY_MAP["js_blocking"], steps, expected, f"Error: {e}; fallback error: {ex}")

# 20 Footer stacking issues on mobile (heuristic)
try:
    steps = "1. Open footer on mobile and check stacking of footer columns."
    expected = "Footer stacks correctly on mobile."
    driver.set_window_size(*MOBILE_SIZE)
    time.sleep(0.6)
    footer = None
    try:
        footer = driver.find_element(By.TAG_NAME, "footer")
    except:
        pass
    if footer:
        # check children width sum
        child_widths = safe_js(driver, "return Array.prototype.slice.call(document.querySelectorAll('footer *')).slice(0,12).map(function(n){return n.getBoundingClientRect().width;});")
        # if many children widths > viewport, maybe stacking issue (not conclusive)
        if child_widths and any(w > MOBILE_SIZE[0] for w in child_widths[:6]):
            add_row(rows, "020", "Footer stacking issues on mobile", SEVERITY_MAP["footer_stack"], steps, expected, "Footer child elements exceed viewport width; possible stacking issue", screenshot="020_Footer.png")
except Exception as e:
    add_row(rows, "020", "Footer stacking check error", SEVERITY_MAP["footer_stack"], steps, expected, f"Error: {e}")

# 21 Font size on mobile (readability)
try:
    steps = "1. Check computed font-size for paragraphs on mobile viewport."
    expected = "Font size should be readable without pinch-zoom (>=14px preferred)."
    driver.set_window_size(*MOBILE_SIZE)
    time.sleep(0.6)
    sizes = safe_js(driver, """
    var ps = document.querySelectorAll('p');
    var out = [];
    for(var i=0;i<Math.min(10,ps.length);i++){ out.push(window.getComputedStyle(ps[i]).getPropertyValue('font-size')); }
    return out;
    """) or []
    smalls = [s for s in sizes if s and s.endswith('px') and float(s.replace('px','')) < 13.5]
    if smalls:
        add_row(rows, "021", "Font size on mobile too small", SEVERITY_MAP["font_size_mobile"], steps, expected, f"Found small font sizes on mobile: {smalls[:6]}", screenshot="021_FontSize.png")
except Exception as e:
    add_row(rows, "021", "Font size check error", SEVERITY_MAP["font_size_mobile"], steps, expected, f"Error: {e}")

# 22 Homepage load performance
try:
    steps = "1. Measure homepage load time using Navigation Timing."
    expected = "Homepage should load within 3 seconds."
    nav = safe_js(driver, "return window.performance.getEntriesByType('navigation')[0] || performance.timing;")
    load_ms = None
    if nav:
        if 'loadEventEnd' in nav and 'navigationStart' in nav:
            load_ms = nav['loadEventEnd'] - nav['navigationStart']
        elif 'duration' in nav:
            load_ms = nav['duration']
    if load_ms is None:
        load_ms = homepage_load_seconds*1000 if homepage_load_seconds else None
    if load_ms and load_ms/1000.0 > 3:
        add_row(rows, "022", "Homepage load performance slow", SEVERITY_MAP["homepage_load"], steps, expected, f"Homepage load time {round(load_ms/1000,2)}s exceeds 3s", screenshot="022_HomepageLoad.png")
except Exception as e:
    add_row(rows, "022", "Homepage load measurement error", SEVERITY_MAP["homepage_load"], steps, expected, f"Error: {e}")

# 23 Unoptimized images (check large image file sizes)
try:
    steps = "1. Detect image resources > 200KB on page (heuristic)."
    expected = "Images should be optimized (small file sizes) and lazy-loaded where appropriate."
    imgs = driver.find_elements(By.TAG_NAME, "img")
    large_imgs = []
    for img in imgs[:60]:
        src = img.get_attribute("src")
        if not src or not src.startswith("http"):
            continue
        try:
            r = requests.head(src, timeout=5)
            size = r.headers.get("Content-Length")
            if size and int(size) > 200000:
                large_imgs.append((src, int(size)))
        except:
            # try GET small part
            try:
                r = requests.get(src, stream=True, timeout=5)
                content = r.content
                if len(content) > 200000:
                    large_imgs.append((src, len(content)))
            except:
                continue
    if large_imgs:
        add_row(rows, "023", "Unoptimized images causing slow rendering", SEVERITY_MAP["unoptimized_images"], steps, expected, f"Large images found sample: {[(x[0], x[1]) for x in large_imgs[:5]]}", screenshot="023_UnoptimizedImages.png")
except Exception as e:
    add_row(rows, "023", "Unoptimized images check error", SEVERITY_MAP["unoptimized_images"], steps, expected, f"Error: {e}")

# 24 Placeholder text visible in Privacy section
try:
    steps = "1. Open Privacy/Contact sections and look for placeholder tokens like 'INSERT'."
    expected = "No placeholder text should be visible on the live site."
    found = []
    texts = driver.find_elements(By.XPATH, "//*[contains(text(),'INSERT') or contains(text(),'INSERT EMAIL') or contains(text(),'INSERT MAILING')]")
    for t in texts[:10]:
        found.append(t.text.strip())
    if found:
        add_row(rows, "024", "Placeholder text visible in Privacy section", SEVERITY_MAP["placeholder_text"], steps, expected, f"Found placeholders: {found[:6]}", screenshot="024_Placeholder.png")
except Exception as e:
    add_row(rows, "024", "Placeholder check error", SEVERITY_MAP["placeholder_text"], steps, expected, f"Error: {e}")

# 25 Twitter icon redirects incorrectly (specific check)
try:
    steps = "1. Click Twitter icon (or inspect href) and check domain it redirects to."
    expected = "Twitter icon should link to official Twitter profile (twitter.com/...)."
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter'], a[href*='x.com']")
    bad = []
    for a in anchors:
        href = a.get_attribute("href")
        if href and 'twitter.com' not in href and 'x.com' not in href:
            bad.append(href)
        # if it goes to x.com, indicate that as an observation per your note
        if href and 'x.com' in href and 'twitter.com' not in href:
            add_row(rows, "025", "Twitter icon redirects to x.com", SEVERITY_MAP["twitter_redirect"], steps, expected, f"Twitter icon links to {href} (x.com) instead of twitter.com", screenshot="025_TwitterLink.png")
except Exception as e:
    add_row(rows, "025", "Twitter link check error", SEVERITY_MAP["twitter_redirect"], steps, expected, f"Error: {e}")

# 26 Extra: Text overlap on mobile (we flagged earlier but ensure detection)
try:
    steps = "1. On mobile, check if any element's bounding boxes overlap (text overlapping buttons/cards)."
    expected = "Text should not overlap with interactive elements."
    driver.set_window_size(*MOBILE_SIZE)
    time.sleep(0.8)
    overlaps = safe_js(driver, """
    function overlap(r1,r2){ return !(r2.left > r1.right || r2.right < r1.left || r2.top > r1.bottom || r2.bottom < r1.top); }
    var elems = Array.prototype.slice.call(document.querySelectorAll('button, a, .card, .article, p')).slice(0,80);
    var pairs=[];
    for(var i=0;i<elems.length;i++){
        try{
            var r1 = elems[i].getBoundingClientRect();
            for(var j=i+1;j<elems.length;j++){
                var r2 = elems[j].getBoundingClientRect();
                if(overlap(r1,r2)){
                    pairs.push([elems[i].outerHTML.slice(0,80), elems[j].outerHTML.slice(0,80)]);
                }
            }
        }catch(e){}
    }
    return pairs.slice(0,6);
    """) or []
    if overlaps:
        add_row(rows, "011b", "Text overlap with interactive elements on mobile", SEVERITY_MAP["text_overlap_mobile"], steps, expected, f"Overlapping element pairs sample: {len(overlaps)}", screenshot="011b_TextOverlapMobile.png")
except Exception as e:
    add_row(rows, "011b", "Text overlap detection error", SEVERITY_MAP["text_overlap_mobile"], steps, expected, f"Error: {e}")

# -----------------------
# Finalize: write Excel
# -----------------------
try:
    df = pd.DataFrame(rows)
    # if empty, add a minimal row so Excel isn't blank
    if df.empty:
        df = pd.DataFrame([{"Bug ID":"N/A","Bug Title":"No issues detected (automated checks)","Severity":"Info","Steps to Reproduce":"Automated run","Expected Result":"No issues","Actual Result":"No issues","Screenshot":"","Status":"Passed","Environment":platform.platform()}])
    summary = {
        "Metric": ["Total Bugs Reported", "High Severity", "Medium Severity", "Low Severity", "Build Stability", "Recommendation"],
        "Value": [
            len(df),
            len(df[df["Severity"] == "High"]),
            len(df[df["Severity"] == "Medium"]),
            len(df[df["Severity"] == "Low"]),
            "Needs Improvement" if len(df[df['Severity']=='High'])>0 else "Stable",
            "Prioritize High severity issues; fix UI consistency; optimize images & JS; re-test"
        ]
    }
    summary_df = pd.DataFrame(summary)
    env_df = pd.DataFrame({
        "Environment": ["Browser", "OS", "Resolutions Tested", "Script Run Time (s)"],
        "Details": [ "Chrome (via Selenium)", platform.platform(), f"{DESKTOP_SIZE[0]}x{DESKTOP_SIZE[1]}, {MOBILE_SIZE[0]}x{MOBILE_SIZE[1]}", round(time.time() - start_time_script, 2)]
    })
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Bug Report", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        env_df.to_excel(writer, sheet_name="Environment", index=False)
    print("Automation completed. Report saved to:", OUTPUT_FILE)
except Exception as e:
    print("Error writing Excel:", e)
    traceback.print_exc()
finally:
    driver.quit()

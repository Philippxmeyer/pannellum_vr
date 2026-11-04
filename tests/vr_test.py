#!/usr/bin/env python3
"""Browser regression checks: python3 tests/vr_test.py (Playwright + Pillow).
Uses installed Chromium; no browser download. Does not rewrite reference images.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import io
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
Thread(target=server.serve_forever, daemon=True).start()
url = 'http://127.0.0.1:' + str(server.server_port)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--enable-unsafe-swiftshader'])
        for dpr in [1, 2]:
            page = browser.new_page(viewport={'width': 900, 'height': 600}, device_scale_factor=dpr)
            page.goto(url + '/tests/tests.html')
            page.wait_for_function('viewer.isLoaded()')
            page.evaluate("document.getElementById('panorama').style.cssText = 'width:800px;height:400px'; viewer.resize()")
            for scene in ['equirectangular', 'cube', 'multires']:
                page.evaluate('(s) => viewer.loadScene(s)', scene)
                page.wait_for_function('(s) => viewer.getScene() === s && viewer.isLoaded()', arg=scene)
                page.evaluate("viewer.lookAt(0, 0, 100, false); viewer.addHotSpot({pitch:0, yaw:0, type:'info', text:'VR regression'}); document.getElementById('panorama').style.width = '400px'; viewer.resize()")
                page.wait_for_timeout(200)
                page.wait_for_function("!viewer.getRenderer().isLoading()")
                normal = Image.open(io.BytesIO(page.locator('canvas').screenshot(style='.pnlm-ui, .pnlm-hotspot-base { visibility: hidden; }'))).convert('RGB')
                page.evaluate("document.getElementById('panorama').style.width = '800px'; viewer.setVRMode(true).setVROffset(0).resize()")
                page.wait_for_timeout(200)
                page.wait_for_function("!viewer.getRenderer().isLoading()")
                assert page.evaluate("document.querySelectorAll('canvas').length") == 1
                canvas = page.locator('canvas')
                image = Image.open(io.BytesIO(canvas.screenshot(style='.pnlm-vr-button { visibility: hidden; }'))).convert('RGB')
                w, h = image.size
                left, right = image.crop((0, 0, w//2, h)), image.crop((w//2, 0, w, h))
                assert max(ImageStat.Stat(ImageChops.difference(left, right)).mean) < 1, scene
                assert max(ImageStat.Stat(ImageChops.difference(normal, left)).mean) < 4, ('aspect', scene, ImageStat.Stat(ImageChops.difference(normal, left)).mean)
                assert max(ImageStat.Stat(left).stddev) > 10, 'blank rendering: ' + scene
                page.evaluate('viewer.setVROffset(0.1)')
                page.wait_for_timeout(200)
                page.wait_for_function("!viewer.getRenderer().isLoading()")
                shifted = Image.open(io.BytesIO(canvas.screenshot(style='.pnlm-vr-button { visibility: hidden; }'))).convert('RGB')
                # Positive displacement moves left optical center left, right right.
                delta = round(w / 2 * 0.1)
                for eye, direction in [(0, -1), (1, 1)]:
                    a = image.crop((eye*w//2+delta, 0, (eye+1)*w//2-delta, h))
                    b = shifted.crop((eye*w//2+delta+direction*delta, 0, (eye+1)*w//2-delta+direction*delta, h))
                    assert max(ImageStat.Stat(ImageChops.difference(a, b)).mean) < 4, ('offset', scene)
                if scene != 'equirectangular':
                    assert page.locator('.pnlm-hotspot-base').last.is_hidden()
                page.evaluate('viewer.setVRMode(false)')
                page.wait_for_timeout(200)
                assert not page.evaluate('viewer.isVRMode()')
                if scene != 'equirectangular':
                    assert page.locator('.pnlm-hotspot-base').last.is_visible()
            page.set_viewport_size({'width': 450, 'height': 800})
            page.evaluate("document.getElementById('panorama').style.cssText = 'width:401px;height:600px'; viewer.setVRMode(true).resize()")
            page.wait_for_timeout(500)
            page.locator('#panorama').focus()
            page.keyboard.press('Escape')
            assert not page.evaluate('viewer.isVRMode()')
            page.close()
        page = browser.new_page()
        page.goto(url + '/examples/example-vr.htm')
        page.wait_for_function('viewer.isLoaded()')
        page.evaluate("() => { document.getElementById('panorama').requestFullscreen = function() { return Promise.reject(new Error('denied')); }; }")
        page.locator('.pnlm-vr-button').click()
        assert page.evaluate('viewer.isVRMode()')
        page.locator('.pnlm-vr-button').click()
        assert not page.evaluate('viewer.isVRMode()')
        page.goto(url + '/build/pannellum.htm#panorama=../examples/examplepano.jpg&autoLoad=true')
        page.wait_for_function('viewer.isLoaded()')
        page.evaluate('viewer.setVRMode(true)')
        assert page.evaluate('viewer.isVRMode()')
        browser.close()
        print('PASS: both eyes, off-axis shift, three panorama types, DPR 1/2, resize, exit, fullscreen denial, example and build')
finally:
    server.shutdown()
    server.server_close()

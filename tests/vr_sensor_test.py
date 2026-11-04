#!/usr/bin/env python3
"""Simulated iOS permission regression test; requires Playwright and Chromium.
This does not validate real iPhone sensors or Safari.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
root = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--enable-unsafe-swiftshader'])
    page = browser.new_page(user_agent='Mozilla/5.0 (iPhone) Mobile Safari', viewport={'width':800,'height':400})
    def serve(route):
        path = root / route.request.url.split('https://vr.test/')[1].split('?')[0]
        if path.is_file(): route.fulfill(path=str(path))
        else: route.fulfill(status=404, body='')
    page.route('https://vr.test/**', serve)
    page.add_init_script('''window.permissionCalls = 0;
    DeviceMotionEvent.requestPermission = function() { return Promise.resolve('granted'); };
    DeviceOrientationEvent.requestPermission = function() { window.permissionCalls++; return Promise.resolve('granted'); };''')
    page.goto('https://vr.test/examples/example-vr.htm')
    page.wait_for_function('viewer.isLoaded()')
    page.click('#sensors')
    page.wait_for_function('window.permissionCalls === 1 && viewer.isOrientationActive()')
    page.evaluate('viewer.setVRMode(true)')
    page.evaluate('''for (var i=0;i<12;i++) window.dispatchEvent(new DeviceOrientationEvent('deviceorientation', {alpha:10,beta:80,gamma:5}));''')
    page.wait_for_timeout(100)
    assert page.evaluate('viewer.isOrientationActive() && viewer.isVRMode() && Number.isFinite(viewer.getYaw())')
    page.evaluate('viewer.setVRMode(false)')
    assert page.evaluate('viewer.isOrientationActive() && permissionCalls === 1')
    browser.close()
    print('PASS: simulated iOS permission gesture and sensor state across VR entry/exit (not a real iPhone)')

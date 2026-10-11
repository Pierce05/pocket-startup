/* Pixel Office canvas for Pocket Startup
   Reuses sprite matrices and palette directly from docs/design/landing_reference.html.
   Reacts to real SSE events from /api/runs/{id}/events.
*/
(function () {
  const W = 500, H = 280;

  // Helper to compile palette-indexed string rows into offscreen canvas
  function mk(rows, pal) {
    const w = Math.max(...rows.map(r => r.length)), h = rows.length;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const g = c.getContext('2d');
    rows.forEach((r, y) => {
      for (let x = 0; x < r.length; x++) {
        const k = r[x];
        if (pal[k]) {
          g.fillStyle = pal[k];
          g.fillRect(x, y, 1, 1);
        }
      }
    });
    return c;
  }

  const R16 = s => (s + '................').slice(0, 16);
  const BASE = [
    '................',
    '.....KKKKKK.....',
    '....KHHHHHHK....',
    '...KHHHHHHHHK...',
    '...KHSSSSSSHK...',
    '...KSSSSSSSSK...',
    '...KSKSSSSKSK...',
    '...KSSSSSSSSK...',
    '...KSSSMMSSSK...',
    '....KSSSSSSK....',
    '...KKTTTTTTKK...',
    '..KTTTTTTTTTTK..',
    '..KTTTTTTTTTTK..',
    '..KSTTTTTTTTSK..',
    '..KSTTTTTTTTSK..',
    '...KTTTTTTTTK...',
    '...KPPPPPPPPK...',
    '...KPPPKKPPPK...',
    '...KPPK..KPPK...',
    '..KKKK....KKKK..'
  ];

  const over = (rows, m) => {
    const r = rows.slice();
    for (const k in m) r[+k] = R16(m[k]);
    return r;
  };

  const ARMS_UP = {
    11: '..SK' + 'T'.repeat(10) + 'KS',
    13: '..K' + 'T'.repeat(10) + 'K',
    14: '..K' + 'T'.repeat(10) + 'K'
  };

  const PAL = { K: '#0F1226', M: '#B5473F' };

  // Sprite rows from landing_reference.html
  const founderRows = over(BASE, { 4: '..KHHHHHHHHHHHK' });
  const engRows = over(BASE, { 3: '..KAK' + 'HHHHHH' + 'KAK', 4: '..KAK' + 'HSSSSH' + 'KAK', 5: '..KAK' + 'SSSSSS' + 'KAK' });
  const testRows = over(BASE, { 13: '..KSTTTTTTTTSK', 14: '..KATTTTTTTTSK' });
  const cfoRows = over(BASE, { 11: '..K' + 'TTTTAATTTT' + 'K', 12: '..K' + 'TTTTAATTTT' + 'K', 13: '..KS' + 'TTTAATTT' + 'SK', 14: '..KS' + 'TTTAATTT' + 'SK' });

  // Sprites
  const SP = {
    founder: {
      idle: mk(founderRows, { ...PAL, H: '#E5322D', S: '#F2C9A0', T: '#4DA3FF', P: '#5E3A63', A: '#F2B63D', D: '#D9A878' }),
      react: mk(over(founderRows, { ...ARMS_UP, 8: '...KSSMMMMSSK' }), { ...PAL, H: '#E5322D', S: '#F2C9A0', T: '#4DA3FF', P: '#5E3A63', A: '#F2B63D', D: '#D9A878' })
    },
    eng: {
      idle: mk(engRows, { ...PAL, H: '#3B2A4D', S: '#E8B88A', T: '#2E8F8B', P: '#14383A', A: '#F2B63D', D: '#C4905F' }),
      react: mk(over(engRows, { 6: '..' + 'D'.repeat(10) + 'K', 8: '...KSSSSSSSSK' }), { ...PAL, H: '#3B2A4D', S: '#E8B88A', T: '#2E8F8B', P: '#14383A', A: '#F2B63D', D: '#B07A4C' })
    },
    tester: {
      idle: mk(testRows, { ...PAL, H: '#5A3A2A', S: '#C98D63', T: '#2FB36B', P: '#2B3358', A: '#E5322D', D: '#A8704A' }),
      react: mk(over(testRows, { ...ARMS_UP, 8: '...KSSMMMMSSK' }), { ...PAL, H: '#5A3A2A', S: '#C98D63', T: '#2FB36B', P: '#2B3358', A: '#E5322D', D: '#A8704A' })
    },
    cfo: {
      idle: mk(cfoRows, { ...PAL, H: '#8A8FA8', S: '#F2C9A0', T: '#2B3358', P: '#14183A', A: '#E5322D', D: '#D9A878' }),
      react: mk(over(cfoRows, { ...ARMS_UP, 8: '...KSSMMMMSSK' }), { ...PAL, H: '#8A8FA8', S: '#F2C9A0', T: '#2B3358', P: '#14183A', A: '#E5322D', D: '#D9A878' })
    }
  };

  const REC = [
    '................',
    '...KKKKKKKKKK...',
    '...KLLLLLLLLK...',
    '...KOOOOOOOOK...',
    '...KOWWWWWWOK...',
    '...KOOOOOOOOK...',
    '...KOOORROOOK...',
    '...KOOOOOOOOK...',
    '...KDDDDDDDDK...',
    '...KKKKKKKKKK...',
    '..KKKKKKKKKKKK..',
    '..KGGGGGGGGGGK..',
    '..KGGKKKKKKGGK..',
    '..KGGGGGGGGGGK..',
    '..KKKKKKKKKKKK..'
  ];
  const recPal = r => ({ K: '#0F1226', L: '#FFC27A', O: '#F2862B', D: '#C0611A', W: '#FFFDF8', R: r, G: '#8A8FA8' });
  SP.rec = {
    dim: mk(REC, recPal('#6E2420')),
    on: mk(REC, recPal('#FF4A3D'))
  };

  SP.laptop = mk([
    '..KKKKKKKKKKKK..',
    '..KNNNNNNNNNNK..',
    '..KNNYNNNNNYNK..',
    '..KNNNNNNNNNNK..',
    '..KNNNNNYNNNNK..',
    '..KNNNNNNNNNNK..',
    '..KKKKKKKKKKKK..',
    '.KWWWWWWWWWWWWK.',
    '.KWKWKWKWKWKWWK.',
    '.KKKKKKKKKKKKKK.'
  ], { K: '#0F1226', N: '#1E3F8A', Y: '#F2B63D', W: '#FFFFFF' });

  const WB_BUILDINGS = [
    [202, 14, 26, '#2E8F8B'],
    [218, 12, 40, '#EF6F5E'],
    [232, 16, 22, '#5E3A63'],
    [250, 10, 34, '#F2B63D'],
    [262, 16, 48, '#4DA3FF'],
    [282, 12, 30, '#2FB36B'],
    [296, 16, 40, '#EF6F5E'],
    [310, 6, 24, '#2E8F8B']
  ];
  const CONFETTI_COLORS = ['#E5322D', '#F2B63D', '#2FB36B', '#4DA3FF', '#EF6F5E', '#5E3A63'];

  class PixelOffice {
    constructor(canvas) {
      this.cv = canvas;
      this.ctx = canvas.getContext('2d');
      this.ctx.imageSmoothingEnabled = false;

      this.t = 0;
      this.last = performance.now();

      this.reset();
      requestAnimationFrame(n => this.frame(n));
    }

    reset() {
      this.idea = '';
      this.spec = null;
      this.attempt = 0;
      this.maxAttempts = 4;
      this.typing = false;
      this.facepalm = false;

      // Positions
      this.founderPos = { x: 42, y: 165 };
      this.founderBubble = null;
      this.founderReact = false;

      this.engPos = { x: 170, y: 126 };
      this.codeLines = 0;

      this.testerHome = 352;
      this.testerPos = { x: 352, y: 175 };
      this.testerTarget = 352;
      this.testerReact = false;
      this.testerClipboard = false;

      this.cfoHome = 520;
      this.cfoPos = { x: 520, y: 177 };
      this.cfoTarget = 520;
      this.cfoReact = false;
      this.cfoVisible = false;

      // Alarms & effects
      this.alarmColor = '#7B7F99';
      this.alarmGlow = null;
      this.alarmDuration = 0;

      this.shakeDuration = 0;
      this.errorBubble = null;

      this.recLit = 0;
      this.crashReport = null;
      this.patchTag = null;

      this.passStamp = false;
      this.passStampDuration = 0;

      this.verdictStamp = null;
      this.verdictDuration = 0;

      this.confetti = [];
      this.statusText = 'idle';
    }

    burst() {
      for (let i = 0; i < 46; i++) {
        this.confetti.push({
          x: 170 + Math.random() * 150,
          y: 40 + Math.random() * 30,
          vx: (Math.random() - 0.5) * 80,
          vy: Math.random() * 50 + 40,
          c: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
          life: 2.5
        });
      }
    }

    handle(type, d) {
      d = d || {};
      switch (type) {
        case 'run_started':
          this.reset();
          this.idea = d.idea || 'an app idea';
          this.founderBubble = this.idea;
          this.founderReact = true;
          this.statusText = 'planning';
          setTimeout(() => { this.founderReact = false; }, 2000);
          break;

        case 'plan':
          this.spec = d.product_name || d.template || 'Spec ready';
          this.statusText = 'building';
          break;

        case 'attempt_started':
          this.attempt = d.n || 1;
          this.maxAttempts = d.of || 4;
          this.typing = true;
          this.facepalm = false;
          this.testerTarget = this.testerHome;
          this.testerClipboard = false;
          this.statusText = `attempt ${this.attempt}`;
          break;

        case 'code_written':
          this.typing = true;
          this.codeLines = Math.min(24, Math.floor((d.bytes || 500) / 100));
          this.statusText = 'verifying';
          break;

        case 'check_started':
          this.typing = false;
          this.testerClipboard = true;
          this.testerTarget = 236; // Walk over to engineer workstation
          this.statusText = 'browser test running';
          break;

        case 'check_failed':
          this.alarmColor = '#FF4A3D';
          this.alarmGlow = 'rgba(255,74,61,0.35)';
          this.alarmDuration = 2.8;
          this.shakeDuration = 0.45;
          this.testerReact = true;
          this.errorBubble = `${d.test || 'check failed'}: ${String(d.actual || 'error').slice(0, 36)}`;
          this.statusText = 'check failed';
          setTimeout(() => { this.testerReact = false; }, 1800);
          break;

        case 'autopsy':
          this.recLit = 3.5;
          this.crashReport = {
            root: d.root_cause ? d.root_cause.slice(0, 32) : 'handler crash',
            change: d.recommended_prompt_change ? d.recommended_prompt_change.slice(0, 32) : 'rule added'
          };
          this.statusText = 'diagnosing';
          break;

        case 'retry':
          this.facepalm = true;
          this.patchTag = '+1 prompt rule';
          this.errorBubble = null;
          this.statusText = 'retrying';
          setTimeout(() => { this.facepalm = false; this.patchTag = null; }, 2200);
          break;

        case 'check_passed':
          this.alarmColor = '#2FD07A';
          this.alarmGlow = 'rgba(47,208,122,0.35)';
          this.alarmDuration = 3.0;
          this.passStamp = true;
          this.passStampDuration = 3.5;
          this.typing = false;
          this.testerTarget = this.testerHome;
          this.testerClipboard = false;
          this.errorBubble = null;
          this.crashReport = null;
          this.burst();
          this.statusText = 'checks passed';
          break;

        case 'awaiting_approval':
          this.founderBubble = 'Approve this build?';
          this.founderReact = true;
          this.statusText = 'awaiting approval';
          break;

        case 'approved':
          this.founderBubble = 'Approved ✔';
          this.founderReact = true;
          this.burst();
          this.statusText = 'approved';
          setTimeout(() => { this.founderBubble = null; this.founderReact = false; }, 3000);
          break;

        case 'metrics_ready':
          this.cfoVisible = true;
          this.cfoTarget = 366;
          this.cfoReact = true;
          setTimeout(() => { this.cfoReact = false; }, 2500);
          break;

        case 'verdict_ready':
          this.verdictStamp = d.verdict || 'BUILD';
          this.verdictDuration = 5.0;
          this.cfoVisible = true;
          this.cfoTarget = 366;
          break;

        case 'run_finished':
          this.typing = false;
          this.statusText = d.success ? 'passed' : 'finished';
          break;
      }
    }

    frame(now) {
      const dt = Math.min(0.05, (now - this.last) / 1000);
      this.last = now;
      this.t += dt;

      this.update(dt);
      this.draw();
      requestAnimationFrame(n => this.frame(n));
    }

    update(dt) {
      // Tester walking interpolation
      if (Math.abs(this.testerPos.x - this.testerTarget) > 1) {
        const dir = Math.sign(this.testerTarget - this.testerPos.x);
        this.testerPos.x += dir * 90 * dt;
      } else {
        this.testerPos.x = this.testerTarget;
      }

      // CFO walking interpolation
      if (this.cfoVisible) {
        if (Math.abs(this.cfoPos.x - this.cfoTarget) > 1) {
          const dir = Math.sign(this.cfoTarget - this.cfoPos.x);
          this.cfoPos.x += dir * 85 * dt;
        } else {
          this.cfoPos.x = this.cfoTarget;
        }
      }

      // Timer updates
      this.shakeDuration = Math.max(0, this.shakeDuration - dt);
      this.alarmDuration = Math.max(0, this.alarmDuration - dt);
      if (this.alarmDuration === 0) {
        this.alarmColor = '#7B7F99';
        this.alarmGlow = null;
      }
      this.recLit = Math.max(0, this.recLit - dt);
      this.passStampDuration = Math.max(0, this.passStampDuration - dt);
      if (this.passStampDuration === 0) this.passStamp = false;

      this.verdictDuration = Math.max(0, this.verdictDuration - dt);

      // Confetti updates
      this.confetti = this.confetti.filter(p => (p.life -= dt) > 0);
      for (const p of this.confetti) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
      }
    }

    R(x, y, w, h, c) {
      this.ctx.fillStyle = c;
      this.ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
    }

    spr(c, x, y, s = 2, flip = false) {
      const w = c.width * s, h = c.height * s;
      if (flip) {
        this.ctx.save();
        this.ctx.translate(Math.round(x) + w, Math.round(y));
        this.ctx.scale(-1, 1);
        this.ctx.drawImage(c, 0, 0, w, h);
        this.ctx.restore();
      } else {
        this.ctx.drawImage(c, Math.round(x), Math.round(y), w, h);
      }
    }

    T(s, x, y, size, col, font = '"JetBrains Mono", monospace', align = 'left') {
      this.ctx.font = size + 'px ' + font;
      this.ctx.fillStyle = col;
      this.ctx.textBaseline = 'top';
      this.ctx.textAlign = align;
      this.ctx.fillText(s, Math.round(x), Math.round(y));
    }

    drawBubble(x, y, w, h, col, tx, ty) {
      this.R(x + 3, y + 3, w, h, 'rgba(15,18,38,0.25)');
      this.R(x - 2, y - 2, w + 4, h + 4, '#0F1226');
      this.R(x, y, w, h, col);
      this.R(tx - 3, ty - 6, 6, 6, col);
    }

    draw() {
      const ctx = this.ctx;
      ctx.save();

      // Screen shake on check failure
      if (this.shakeDuration > 0) {
        const sx = (Math.random() * 6 - 3) | 0;
        const sy = (Math.random() * 4 - 2) | 0;
        ctx.translate(sx, sy);
      }

      // 1. Wall and Floor
      this.R(0, 0, W, 180, '#F3EAD7');
      this.R(0, 120, W, 46, '#EBDDBF');
      this.R(0, 164, W, 8, '#D9C9A8');
      this.R(0, 172, W, 110, '#CDB892');
      for (let x = 0; x < W; x += 40) this.R(x, 172, 2, 108, '#C2AC84');
      this.R(0, 214, W, 2, '#C2AC84');

      // 2. Whiteboard (x: 16, y: 18)
      this.R(16, 18, 140, 78, '#0F1226');
      this.R(18, 20, 136, 74, '#FFFFFF');
      this.R(24, 96, 124, 4, '#8A8FA8');
      this.T('IDEAS', 24, 24, 8, '#0F1226', '"Pixelify Sans", monospace');

      // Sticky notes on whiteboard
      this.R(24, 38, 36, 22, '#EF6F5E');
      this.R(68, 38, 36, 22, '#F2B63D');
      this.R(112, 38, 36, 22, '#4DA3FF');
      for (let i = 0; i < 4; i++) {
        this.R(24, 66 + i * 6, (i * 24 + 40) % 90, 2, '#C9C4D6');
      }

      // Spec card on board
      if (this.spec) {
        this.R(100, 30, 48, 38, '#FFFDF8');
        this.R(98, 28, 52, 42, '#0F1226');
        this.R(100, 30, 48, 38, '#FFFDF8');
        this.R(100, 30, 48, 4, '#E5322D');
        this.T('SPEC', 104, 36, 7, '#0F1226', '"Pixelify Sans", monospace');
        const shortSpec = this.spec.slice(0, 14);
        this.T(shortSpec, 104, 46, 6, '#454963');
      }

      // 3. Skyline Window (x: 196, y: 14)
      this.R(196, 14, 124, 86, '#0F1226');
      this.R(200, 18, 116, 78, '#BFE3F5');
      this.R(200, 56, 116, 40, '#F9DCC4');
      this.R(296, 24, 10, 10, '#FFF1A8'); // sun / moon

      // Skyline buildings
      WB_BUILDINGS.forEach((b, bi) => {
        const [bx, bw, bh, bc] = b, by = 96 - bh;
        this.R(bx, by, bw, bh, bc);
        for (let c = 0; c < Math.floor((bw - 4) / 4); c++) {
          for (let r = 0; r < Math.floor((bh - 4) / 5); r++) {
            const lit = (bi * 7 + r * 3 + c * 5) % 3 === 0;
            this.R(bx + 3 + c * 4, by + 3 + r * 5, 2, 3, lit ? '#FFF1A8' : 'rgba(15,18,38,0.3)');
          }
        }
      });
      this.R(257, 18, 3, 78, '#0F1226'); // Window mullion vertical
      this.R(200, 56, 116, 3, '#0F1226'); // Window mullion horizontal

      // 4. Engineer Desk & Station (x: 150, y: 156)
      const engBob = this.typing ? (Math.floor(this.t * 7) % 2) : 0;
      this.spr(this.facepalm ? SP.eng.react : SP.eng.idle, this.engPos.x, this.engPos.y + engBob, 2, false);

      this.R(150, 156, 176, 10, '#8B5E3C');
      this.R(150, 156, 176, 2, '#B07B4F');
      this.R(154, 166, 168, 26, '#6F4A2E');
      this.R(160, 172, 70, 14, '#5E3E26');
      this.R(240, 172, 70, 14, '#5E3E26');
      this.R(190, 178, 10, 2, '#C9B27C');
      this.R(270, 178, 10, 2, '#C9B27C');
      this.R(150, 192, 176, 4, 'rgba(15,18,38,0.18)');

      // Monitor & Screen
      this.R(228, 146, 10, 10, '#2B3358');
      this.R(200, 102, 66, 44, '#0F1226');
      this.R(201, 103, 64, 42, '#2B3358');

      // Monitor Screen content
      const sx = 203, sy = 105, sw = 60, sh = 36;
      this.R(sx, sy, sw, sh, '#14183A');
      if (this.typing) {
        const cols = ['#4DA3FF', '#F2B63D', '#2FB36B', '#EF6F5E', '#C9C4D6'];
        const off = (this.t * 14) % 5;
        for (let i = 0; i < 7; i++) {
          const y = sy + 2 + i * 5 - off;
          if (y < sy || y > sy + sh - 3) continue;
          const w = 10 + ((i + Math.floor(this.t * 4)) * 17) % 36;
          this.R(sx + 3, y, Math.min(w, sw - 6), 2, cols[(i + Math.floor(this.t)) % 5]);
        }
      } else if (this.passStamp) {
        this.R(sx, sy, sw, sh, '#FFFDF8');
        this.R(sx, sy, sw, 6, '#2E8F8B');
        this.T('PASS', sx + 18, sy + 14, 10, '#1B8548', '"Pixelify Sans", monospace');
      } else {
        if (Math.floor(this.t * 2) % 2 === 0) this.T('>_', sx + 4, sy + 4, 8, '#8CF0B4');
      }

      // Keyboard & Laptop
      this.R(204, 152, 50, 4, '#C9C4D6');
      if (this.typing) {
        for (let i = 0; i < 6; i++) {
          if ((Math.floor(this.t * 12) + i) % 3 === 0) this.R(206 + i * 8, 152, 3, 2, '#FFFFFF');
        }
      }
      this.spr(SP.laptop, 278, 136, 2, false);

      // 5. Shelf, Flight Recorder & Alarm Lamp
      this.R(414, 78, 64, 5, '#8B5E3C');
      this.R(420, 83, 4, 10, '#6F4A2E');
      this.R(468, 83, 4, 10, '#6F4A2E');

      // Flight recorder black box
      const recOn = this.recLit > 0 || (Math.floor(this.t * 2) % 2 === 0 && this.statusText === 'building');
      this.spr(recOn ? SP.rec.on : SP.rec.dim, 428, 48, 2, false);

      // Alarm Lamp
      if (this.alarmGlow) {
        ctx.fillStyle = this.alarmGlow;
        ctx.fillRect(436, 10, 36, 36);
      }
      this.R(446, 22, 12, 12, '#2B3358');
      this.R(448, 24, 8, 8, this.alarmColor);
      this.R(450, 34, 4, 4, '#2B3358');

      // 6. Financial Chart Board (x: 398, y: 132)
      this.R(402, 176, 3, 40, '#6F4A2E');
      this.R(458, 176, 3, 40, '#6F4A2E');
      this.R(398, 132, 66, 52, '#0F1226');
      this.R(400, 134, 62, 48, '#FFFDF8');
      this.R(404, 176, 54, 1, '#8A8FA8');

      const barHeights = [14, 26, 18, 34];
      const barCols = ['#4DA3FF', '#2FB36B', '#F2B63D', '#EF6F5E'];
      for (let i = 0; i < 4; i++) {
        this.R(408 + i * 13, 176 - barHeights[i], 9, barHeights[i], barCols[i]);
      }
      this.T('CFO', 404, 137, 7, '#5E3A63', '"Pixelify Sans", monospace');

      // 7. Characters
      const walkBob = x => Math.floor(x / 6) % 2;

      // Founder
      const founderBob = Math.floor(this.t * 2) % 2;
      this.spr(this.founderReact ? SP.founder.react : SP.founder.idle, this.founderPos.x, this.founderPos.y + founderBob, 2, false);

      // Tester
      const testerMoving = Math.abs(this.testerPos.x - this.testerTarget) > 1;
      const testerBob = testerMoving ? walkBob(this.testerPos.x) : (Math.floor(this.t * 2) % 2);
      this.spr(this.testerReact ? SP.tester.react : SP.tester.idle, this.testerPos.x, this.testerPos.y + testerBob, 2, testerMoving);

      if (this.testerClipboard) {
        this.R(this.testerPos.x + 28, this.testerPos.y + testerBob + 18, 10, 13, '#7A4E2D');
        this.R(this.testerPos.x + 30, this.testerPos.y + testerBob + 20, 6, 9, '#FFFDF8');
      }

      // CFO
      if (this.cfoVisible) {
        const cfoMoving = Math.abs(this.cfoPos.x - this.cfoTarget) > 1;
        const cfoBob = cfoMoving ? walkBob(this.cfoPos.x) : (Math.floor(this.t * 2) % 2);
        this.spr(this.cfoReact ? SP.cfo.react : SP.cfo.idle, this.cfoPos.x, this.cfoPos.y + cfoBob, 2, false);
      }

      // 8. Bubbles & Overlays
      // Founder Idea Bubble
      if (this.founderBubble) {
        const txt = this.founderBubble.slice(0, 36);
        this.drawBubble(20, 106, 126, 36, '#FFFFFF', 66, 150);
        this.T(txt.slice(0, 18), 26, 111, 8, '#0F1226');
        if (txt.length > 18) {
          this.T(txt.slice(18, 36), 26, 123, 8, '#0F1226');
        }
      }

      // Error Bubble
      if (this.errorBubble) {
        this.drawBubble(260, 94, 96, 32, '#FFE9E6', 250, 128);
        this.T('FAIL', 265, 98, 8, '#CF2A25', '"Pixelify Sans", monospace');
        this.T(this.errorBubble.slice(0, 16), 265, 110, 7, '#0F1226');
      }

      // Crash Report Card
      if (this.crashReport) {
        const cx = 330, cy = 96;
        this.R(cx + 3, cy + 3, 92, 54, 'rgba(15,18,38,0.25)');
        this.R(cx - 2, cy - 2, 96, 58, '#0F1226');
        this.R(cx, cy, 92, 54, '#FFFDF8');
        this.R(cx, cy, 92, 10, '#CF2A25');
        this.T('CRASH REPORT', cx + 4, cy + 1, 7, '#FFFFFF', '"Pixelify Sans", monospace');
        this.T('ROOT: ' + this.crashReport.root, cx + 4, cy + 15, 6, '#0F1226');
        this.T('FIX: ' + this.crashReport.change, cx + 4, cy + 30, 6, '#1B8548');
      }

      // Patch Tag
      if (this.patchTag) {
        this.T(this.patchTag, 236, 92, 9, '#1B8548', '"Pixelify Sans", monospace');
      }

      // PASS Stamp
      if (this.passStamp) {
        ctx.save();
        ctx.translate(290, 119);
        ctx.rotate(-8 * Math.PI / 180);
        this.R(2, 2, 42, 16, 'rgba(15,18,38,0.3)');
        this.R(-21, -8, 42, 16, '#1B8548');
        this.T('PASS', 0, -5, 10, '#FFFFFF', '"Pixelify Sans", monospace', 'center');
        ctx.restore();
      }

      // Giant Rotated Verdict Stamp
      if (this.verdictStamp && this.verdictDuration > 0) {
        const col = this.verdictStamp === 'BUILD' ? '#1B8548' : this.verdictStamp === 'KILL' ? '#CF2A25' : '#F2B63D';
        const txtCol = this.verdictStamp === 'PIVOT' ? '#0F1226' : '#FFFFFF';
        ctx.save();
        ctx.translate(350, 56);
        ctx.rotate(-9 * Math.PI / 180);
        this.R(-42, -16, 90, 34, 'rgba(15,18,38,0.35)');
        this.R(-44, -18, 90, 34, '#0F1226');
        this.R(-42, -16, 86, 30, col);
        ctx.strokeStyle = txtCol;
        ctx.lineWidth = 1;
        ctx.strokeRect(-38.5, -12.5, 79, 23);
        this.T(this.verdictStamp, 2, -8, 16, txtCol, '"Pixelify Sans", monospace', 'center');
        ctx.restore();
      }

      // Confetti
      for (const p of this.confetti) {
        this.R(p.x, p.y, 3, 3, p.c);
      }

      ctx.restore();
    }
  }

  window.PixelOffice = PixelOffice;
})();

/**
 * MSME Digital Transformation - Business Data Analytics Background Engine
 * Continuous, smooth canvas & SVG business intelligence visual concept
 * strictly adhering to color, opacity, animation, and interaction guidelines.
 */

(function () {
    'use strict';

    const canvas = document.getElementById("loginBgCanvas");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Check accessibility setting
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let isReducedMotion = motionQuery.matches;

    motionQuery.addEventListener("change", (e) => {
        isReducedMotion = e.matches;
        if (isReducedMotion && animFrameId) {
            cancelAnimationFrame(animFrameId);
            renderStaticFrame();
        } else if (!isReducedMotion) {
            startLoop();
        }
    });

    // Color definitions (Strict adherence to specified palette)
    // Deep Teal: #0F766E, Light Teal: #14B8A6, Very Light Teal: #CCFBF1
    const COLOR_DEEP_TEAL = "15, 118, 110";
    const COLOR_LIGHT_TEAL = "20, 184, 166";
    const COLOR_VERY_LIGHT_TEAL = "204, 251, 241";

    let width = 0;
    let height = 0;
    let dpr = 1;
    let animFrameId = null;
    let time = 0;

    // Smooth Mouse Tracking with Damped Interpolation (Lerp)
    let targetMouseX = window.innerWidth / 2;
    let targetMouseY = window.innerHeight / 2;
    let currentMouseX = targetMouseX;
    let currentMouseY = targetMouseY;

    document.addEventListener("mousemove", (e) => {
        targetMouseX = e.clientX;
        targetMouseY = e.clientY;
    });

    // Touch support for mobile mouse position
    document.addEventListener("touchmove", (e) => {
        if (e.touches && e.touches[0]) {
            targetMouseX = e.touches[0].clientX;
            targetMouseY = e.touches[0].clientY;
        }
    }, { passive: true });

    // Data structures for 9 visual elements
    let gridOffset = 0;
    let lineChart1 = [];
    let lineChart2 = [];
    let chartDataPoints = [];
    let barColumns = [];
    let networkNodes = [];
    let nodePackets = [];
    let growthIndicators = [];

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        width = canvas.clientWidth || window.innerWidth;
        height = canvas.clientHeight || window.innerHeight;
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);

        initElements();
    }

    function initElements() {
        const isMobile = width < 768;
        const isTablet = width >= 768 && width < 1024;

        // 1. Thin Business Line Chart 1 (Sales Trend Curve across background)
        const pointCount1 = isMobile ? 8 : (isTablet ? 14 : 20);
        lineChart1 = [];
        for (let i = 0; i <= pointCount1; i++) {
            const x = (width / pointCount1) * i;
            const baseY = height * 0.58 + Math.sin((i / pointCount1) * Math.PI * 2.2) * (height * 0.12);
            lineChart1.push({
                x: x,
                baseY: baseY,
                y: baseY,
                speed: 0.0012 + (i % 3) * 0.0003,
                phase: i * 0.4
            });
        }

        // Line Chart 2 (Revenue / Growth Trend Curve)
        const pointCount2 = isMobile ? 6 : (isTablet ? 12 : 16);
        lineChart2 = [];
        for (let i = 0; i <= pointCount2; i++) {
            const x = (width / pointCount2) * i;
            const baseY = height * 0.38 + Math.cos((i / pointCount2) * Math.PI * 1.8) * (height * 0.10);
            lineChart2.push({
                x: x,
                baseY: baseY,
                y: baseY,
                speed: 0.0009 + (i % 2) * 0.0004,
                phase: i * 0.5 + 1.2
            });
        }

        // 2. Data Points Moving Along Chart Lines
        chartDataPoints = [
            { chartIndex: 1, progress: 0.15, speed: 0.0008, radius: 3.5 },
            { chartIndex: 1, progress: 0.65, speed: 0.0011, radius: 3.5 },
            { chartIndex: 2, progress: 0.35, speed: 0.0009, radius: 3.0 },
            { chartIndex: 2, progress: 0.85, speed: 0.0007, radius: 3.0 }
        ];

        // 3. Subtle Animated Bar-Chart Columns (Rising and Falling)
        const colCount = isMobile ? 10 : (isTablet ? 18 : 28);
        const colWidth = isMobile ? 10 : 14;
        const gap = isMobile ? 6 : 10;
        const totalWidth = colCount * (colWidth + gap);
        const startX = width > 1200 ? width * 0.04 : (width - totalWidth) / 2;
        barColumns = [];
        for (let i = 0; i < colCount; i++) {
            barColumns.push({
                x: startX + i * (colWidth + gap),
                width: colWidth,
                baseHeight: 20 + (Math.sin(i * 0.4) * 15 + 15),
                maxHeight: 70 + (Math.cos(i * 0.6) * 35 + 25),
                speed: 0.0012 + (i % 4) * 0.0004,
                phase: i * 0.35
            });
        }

        // 4. Glowing Network Nodes & Data Connections
        const nodeCount = isMobile ? 12 : (isTablet ? 22 : 36);
        networkNodes = [];
        for (let i = 0; i < nodeCount; i++) {
            networkNodes.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.35,
                vy: (Math.random() - 0.5) * 0.35,
                radius: 2 + Math.random() * 2,
                pulse: Math.random() * Math.PI * 2,
                pulseSpeed: 0.02 + Math.random() * 0.02
            });
        }

        // 5. Data Packets traveling along network connections
        const packetCount = isMobile ? 3 : (isTablet ? 6 : 10);
        nodePackets = [];
        for (let i = 0; i < packetCount; i++) {
            nodePackets.push({
                fromIndex: Math.floor(Math.random() * nodeCount),
                toIndex: Math.floor(Math.random() * nodeCount),
                progress: Math.random(),
                speed: 0.003 + Math.random() * 0.005
            });
        }

        // 6. Very Subtle Upward Growth Indicators (↗ / ▲)
        const arrowCount = isMobile ? 4 : (isTablet ? 8 : 14);
        growthIndicators = [];
        for (let i = 0; i < arrowCount; i++) {
            growthIndicators.push({
                x: Math.random() * width,
                y: Math.random() * height,
                speedY: 0.2 + Math.random() * 0.3,
                speedX: (Math.random() - 0.5) * 0.1,
                size: 9 + Math.random() * 5,
                opacity: 0.05 + Math.random() * 0.08,
                symbol: Math.random() > 0.45 ? "↗" : "▲"
            });
        }
    }

    // Helper: Interpolate point along bezier/catmull line
    function getPointOnLine(points, t) {
        if (!points || points.length === 0) return { x: 0, y: 0 };
        const clampedT = Math.max(0, Math.min(1, t));
        const indexFloat = clampedT * (points.length - 1);
        const idx = Math.floor(indexFloat);
        const frac = indexFloat - idx;
        const p1 = points[idx];
        const p2 = points[Math.min(idx + 1, points.length - 1)];

        // Smooth cosine interpolation for natural curves
        const mu2 = (1 - Math.cos(frac * Math.PI)) / 2;
        return {
            x: p1.x * (1 - frac) + p2.x * frac,
            y: p1.y * (1 - mu2) + p2.y * mu2
        };
    }

    function renderGrid() {
        // Subtle animated grid moving extremely slowly (5–8% opacity)
        gridOffset = (gridOffset + 0.12) % 40;
        ctx.lineWidth = 1;
        ctx.strokeStyle = `rgba(${COLOR_DEEP_TEAL}, 0.06)`;

        const gridSize = 40;
        ctx.beginPath();

        // Vertical Grid Lines
        for (let x = gridOffset; x < width; x += gridSize) {
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
        }

        // Horizontal Grid Lines
        for (let y = gridOffset; y < height; y += gridSize) {
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
        }
        ctx.stroke();
    }

    function renderBarColumns() {
        // Subtle animated bar-chart columns that slowly rise and fall (10–18% opacity)
        for (let i = 0; i < barColumns.length; i++) {
            const bar = barColumns[i];
            const wave = Math.sin(time * bar.speed + bar.phase);
            const currentH = bar.baseHeight + ((wave + 1) / 2) * (bar.maxHeight - bar.baseHeight);
            const y = height - currentH - 24;

            // Bar Column Base
            ctx.fillStyle = `rgba(${COLOR_DEEP_TEAL}, 0.08)`;
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(bar.x, y, bar.width, currentH, [3, 3, 0, 0]);
            } else {
                ctx.rect(bar.x, y, bar.width, currentH);
            }
            ctx.fill();

            // Highlight top cap of column
            ctx.fillStyle = `rgba(${COLOR_LIGHT_TEAL}, 0.16)`;
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(bar.x, y, bar.width, 4, [3, 3, 0, 0]);
            } else {
                ctx.rect(bar.x, y, bar.width, 4);
            }
            ctx.fill();
        }
    }

    function renderLineCharts() {
        // 1. Line Chart 1 (Sales)
        for (let i = 0; i < lineChart1.length; i++) {
            const p = lineChart1[i];
            // Base sine oscillation
            const waveY = p.baseY + Math.sin(time * p.speed + p.phase) * 16;
            
            // Mouse interaction: subtle reaction when cursor is nearby
            const dx = p.x - currentMouseX;
            const dy = waveY - currentMouseY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const mouseEffectRadius = 180;
            let mouseShift = 0;
            if (dist < mouseEffectRadius) {
                const factor = 1 - dist / mouseEffectRadius;
                mouseShift = -16 * Math.sin(factor * Math.PI);
            }
            p.y = waveY + mouseShift;
        }

        // Draw Line Chart 1 Curve & Area (10-18% opacity)
        ctx.beginPath();
        ctx.moveTo(lineChart1[0].x, lineChart1[0].y);
        for (let i = 0; i < lineChart1.length - 1; i++) {
            const xc = (lineChart1[i].x + lineChart1[i + 1].x) / 2;
            const yc = (lineChart1[i].y + lineChart1[i + 1].y) / 2;
            ctx.quadraticCurveTo(lineChart1[i].x, lineChart1[i].y, xc, yc);
        }
        const lastP1 = lineChart1[lineChart1.length - 1];
        ctx.lineTo(lastP1.x, lastP1.y);

        ctx.lineWidth = 2.2;
        ctx.strokeStyle = `rgba(${COLOR_DEEP_TEAL}, 0.18)`;
        ctx.stroke();

        // Area Fill under Chart 1
        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        const areaGrad = ctx.createLinearGradient(0, height * 0.4, 0, height);
        areaGrad.addColorStop(0, `rgba(${COLOR_DEEP_TEAL}, 0.05)`);
        areaGrad.addColorStop(1, `rgba(${COLOR_DEEP_TEAL}, 0.00)`);
        ctx.fillStyle = areaGrad;
        ctx.fill();

        // 2. Line Chart 2 (Revenue / Growth)
        for (let i = 0; i < lineChart2.length; i++) {
            const p = lineChart2[i];
            const waveY = p.baseY + Math.cos(time * p.speed + p.phase) * 14;

            const dx = p.x - currentMouseX;
            const dy = waveY - currentMouseY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            let mouseShift = 0;
            if (dist < 160) {
                const factor = 1 - dist / 160;
                mouseShift = -12 * Math.sin(factor * Math.PI);
            }
            p.y = waveY + mouseShift;
        }

        ctx.beginPath();
        ctx.moveTo(lineChart2[0].x, lineChart2[0].y);
        for (let i = 0; i < lineChart2.length - 1; i++) {
            const xc = (lineChart2[i].x + lineChart2[i + 1].x) / 2;
            const yc = (lineChart2[i].y + lineChart2[i + 1].y) / 2;
            ctx.quadraticCurveTo(lineChart2[i].x, lineChart2[i].y, xc, yc);
        }
        const lastP2 = lineChart2[lineChart2.length - 1];
        ctx.lineTo(lastP2.x, lastP2.y);

        ctx.lineWidth = 1.8;
        ctx.strokeStyle = `rgba(${COLOR_LIGHT_TEAL}, 0.16)`;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
    }

    function renderDataPointsOnLines() {
        // Small data points moving along chart lines
        for (let i = 0; i < chartDataPoints.length; i++) {
            const dp = chartDataPoints[i];
            dp.progress = (dp.progress + dp.speed) % 1;

            const linePoints = dp.chartIndex === 1 ? lineChart1 : lineChart2;
            const pos = getPointOnLine(linePoints, dp.progress);

            // Glowing data point
            ctx.fillStyle = `rgba(${COLOR_LIGHT_TEAL}, 0.75)`;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, dp.radius, 0, Math.PI * 2);
            ctx.fill();

            // Subtle outer glow halo (15-25% opacity)
            ctx.strokeStyle = `rgba(${COLOR_LIGHT_TEAL}, 0.25)`;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, dp.radius + 3, 0, Math.PI * 2);
            ctx.stroke();
        }
    }

    function renderNetworkNodesAndConnections() {
        // Small glowing data points moving between different points with thin connecting lines (15–25% opacity)
        const mouseRadius = 200;

        for (let i = 0; i < networkNodes.length; i++) {
            const node = networkNodes[i];

            // Position update
            node.x += node.vx;
            node.y += node.vy;

            // Bounce off boundaries
            if (node.x < 0 || node.x > width) node.vx *= -1;
            if (node.y < 0 || node.y > height) node.vy *= -1;

            // Mouse interaction: nearby data points slightly move toward cursor
            const dx = currentMouseX - node.x;
            const dy = currentMouseY - node.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < mouseRadius && dist > 10) {
                const attractionFactor = (1 - dist / mouseRadius) * 0.015;
                node.x += dx * attractionFactor;
                node.y += dy * attractionFactor;
            }

            // Pulse radius
            node.pulse += node.pulseSpeed;
            const currentR = node.radius + Math.sin(node.pulse) * 0.6;

            // Draw Node
            ctx.fillStyle = `rgba(${COLOR_LIGHT_TEAL}, 0.22)`;
            ctx.beginPath();
            ctx.arc(node.x, node.y, currentR, 0, Math.PI * 2);
            ctx.fill();
        }

        // Draw thin connecting lines between close nodes
        const maxConnectDist = width < 768 ? 100 : 130;
        ctx.lineWidth = 1;
        for (let i = 0; i < networkNodes.length; i++) {
            for (let j = i + 1; j < networkNodes.length; j++) {
                const n1 = networkNodes[i];
                const n2 = networkNodes[j];
                const dx = n1.x - n2.x;
                const dy = n1.y - n2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < maxConnectDist) {
                    const lineOpacity = (1 - dist / maxConnectDist) * 0.12;
                    ctx.strokeStyle = `rgba(${COLOR_DEEP_TEAL}, ${lineOpacity.toFixed(3)})`;
                    ctx.beginPath();
                    ctx.moveTo(n1.x, n1.y);
                    ctx.lineTo(n2.x, n2.y);
                    ctx.stroke();
                }
            }
        }

        // Data Packets moving along network lines
        for (let i = 0; i < nodePackets.length; i++) {
            const packet = nodePackets[i];
            packet.progress += packet.speed;

            if (packet.progress >= 1) {
                packet.progress = 0;
                packet.fromIndex = Math.floor(Math.random() * networkNodes.length);
                packet.toIndex = Math.floor(Math.random() * networkNodes.length);
            }

            const n1 = networkNodes[packet.fromIndex];
            const n2 = networkNodes[packet.toIndex];
            if (n1 && n2) {
                const px = n1.x + (n2.x - n1.x) * packet.progress;
                const py = n1.y + (n2.y - n1.y) * packet.progress;

                ctx.fillStyle = `rgba(${COLOR_LIGHT_TEAL}, 0.60)`;
                ctx.beginPath();
                ctx.arc(px, py, 2.2, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    function renderGrowthIndicators() {
        // Very subtle upward arrows / growth indicators moving slowly upward (5–15% opacity)
        ctx.font = "12px Inter, sans-serif";
        ctx.textAlign = "center";

        for (let i = 0; i < growthIndicators.length; i++) {
            const arrow = growthIndicators[i];
            arrow.y -= arrow.speedY;
            arrow.x += arrow.speedX;

            // Reset when reaching top
            if (arrow.y < -30) {
                arrow.y = height + 30;
                arrow.x = Math.random() * width;
            }

            // Opacity fade in/out near edges
            const verticalRatio = arrow.y / height;
            const fade = Math.sin(verticalRatio * Math.PI);
            const currentOpacity = arrow.opacity * fade;

            ctx.fillStyle = `rgba(${COLOR_DEEP_TEAL}, ${currentOpacity.toFixed(3)})`;
            ctx.fillText(arrow.symbol, arrow.x, arrow.y);
        }
    }

    function updateFloatingKpiCardsAndMouseParallax() {
        // Smooth Damped Mouse Lerp
        currentMouseX += (targetMouseX - currentMouseX) * 0.05;
        currentMouseY += (targetMouseY - currentMouseY) * 0.05;

        // Shift floating KPI cards slightly based on cursor relative to center
        const kpiContainer = document.querySelector(".login-floating-kpis");
        if (kpiContainer) {
            const deltaX = (currentMouseX - width / 2) / (width / 2);
            const deltaY = (currentMouseY - height / 2) / (height / 2);
            kpiContainer.style.transform = `translate3d(${deltaX * 14}px, ${deltaY * 14}px, 0)`;
        }
    }

    function renderStaticFrame() {
        ctx.clearRect(0, 0, width, height);
        renderGrid();
        renderBarColumns();
        renderLineCharts();
        renderDataPointsOnLines();
        renderNetworkNodesAndConnections();
        renderGrowthIndicators();
    }

    function startLoop() {
        function frame() {
            time += 16;
            ctx.clearRect(0, 0, width, height);

            renderGrid();
            renderBarColumns();
            renderLineCharts();
            renderDataPointsOnLines();
            renderNetworkNodesAndConnections();
            renderGrowthIndicators();
            updateFloatingKpiCardsAndMouseParallax();

            if (!isReducedMotion) {
                animFrameId = requestAnimationFrame(frame);
            }
        }
        frame();
    }

    // Periodic Ticker for Floating KPI numbers to convey real-time data processing
    function setupKpiDataTicker() {
        const revEl = document.getElementById("kpiRevenue");
        const custEl = document.getElementById("kpiCustomers");
        const invEl = document.getElementById("kpiInventory");
        const opsEl = document.getElementById("kpiOps");

        let revVal = 148250;
        let custVal = 3420;
        let opsVal = 1420;

        setInterval(() => {
            if (isReducedMotion) return;

            const choice = Math.floor(Math.random() * 3);
            if (choice === 0 && revEl) {
                revVal += Math.floor(Math.random() * 40 + 10);
                revEl.textContent = `$${revVal.toLocaleString("en-US")}`;
                highlightKpi(revEl);
            } else if (choice === 1 && custEl) {
                custVal += Math.floor(Math.random() * 3 + 1);
                custEl.textContent = custVal.toLocaleString("en-US");
                highlightKpi(custEl);
            } else if (choice === 2 && opsEl) {
                opsVal = 1400 + Math.floor(Math.random() * 55);
                opsEl.textContent = `${opsVal.toLocaleString("en-US")} ops/s`;
                highlightKpi(opsEl);
            }
        }, 3600);
    }

    function highlightKpi(element) {
        element.style.color = "#0F766E";
        element.style.transition = "color 0.2s ease";
        setTimeout(() => {
            element.style.color = "";
        }, 800);
    }

    // Initialization
    window.addEventListener("resize", resize);
    resize();
    setupKpiDataTicker();

    if (isReducedMotion) {
        renderStaticFrame();
    } else {
        startLoop();
    }
})();

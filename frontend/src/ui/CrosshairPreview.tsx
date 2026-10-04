import type { ReactNode } from 'react';
import type { Style } from '../bridge';

type ShapeLayerProps = {
  item: Style;
  stroke: string;
  opacity: number;
  line: number;
  circle: number;
  dot: number;
};

function ShapeLayer({ item, stroke, opacity, line, circle, dot }: ShapeLayerProps) {
  const factor = 88 / Math.max(9, item.canvasSize);
  const px = (value: number) => 50 + value * factor;
  const gap = item.gap / 2;
  const arm = item.armLength;
  const customCellSize = item.customCellSize * factor;
  const grid = item.customGridSize * item.customCellSize;
  const cells: ReactNode[] = item.customFilledCells.map(([x, y]) => (
    <rect
      key={`${x}:${y}`}
      x={px(-grid / 2 + x * item.customCellSize)}
      y={px(-grid / 2 + y * item.customCellSize)}
      width={customCellSize}
      height={customCellSize}
      fill={stroke}
    />
  ));
  const parts: ReactNode[] = [];
  const path = (key: string, d: string) => parts.push(
    <path key={key} d={d} fill="none" stroke={stroke} strokeOpacity={opacity} strokeWidth={line * factor} strokeLinecap="square" />,
  );
  const circleShape = (key: string, radius: number) => parts.push(
    <circle key={key} cx="50" cy="50" r={radius * factor} fill="none" stroke={stroke} strokeOpacity={opacity} strokeWidth={circle * factor} />,
  );
  const box = (key: string, half: number) => parts.push(
    <rect key={key} x={px(-half)} y={px(-half)} width={2 * half * factor} height={2 * half * factor} fill="none" stroke={stroke} strokeOpacity={opacity} strokeWidth={line * factor} />,
  );

  if (item.shape === 'classic_cross' || item.shape === 'circle_cross') {
    path('cross-left', `M${px(-gap - arm)} 50H${px(-gap)}`);
    path('cross-right', `M${px(gap)} 50H${px(gap + arm)}`);
    if (!item.tStyle) path('cross-top', `M50 ${px(-gap - arm)}V${px(-gap)}`);
    path('cross-bottom', `M50 ${px(gap)}V${px(gap + arm)}`);
  }
  if (item.shape === 'circle_cross' || item.shape === 'ring') circleShape('ring', item.circleRadius);
  if (item.shape === 'bracket') {
    const l = -gap; const r = gap; const t = -gap; const b = gap;
    path('bracket-tl', `M${px(l-arm)} ${px(t)}H${px(l)}V${px(t-arm)}`);
    path('bracket-tr', `M${px(r)} ${px(t-arm)}V${px(t)}H${px(r+arm)}`);
    path('bracket-bl', `M${px(l-arm)} ${px(b)}H${px(l)}V${px(b+arm)}`);
    path('bracket-br', `M${px(r)} ${px(b+arm)}V${px(b)}H${px(r+arm)}`);
  }
  if (item.shape === 'square') box('square', Math.max(2, gap + arm / 2));
  if (item.shape === 'diamond') {
    const half = Math.max(2, arm / 2 + item.gap / 3);
    path('diamond', `M50 ${px(-half)}L${px(half)} 50 50 ${px(half)} ${px(-half)} 50Z`);
  }
  if (item.shape === 'custom_grid') parts.push(...cells);
  if (item.dot || item.shape === 'dot') {
    const radius = dot * factor / 2;
    parts.push(<circle key="center-dot" cx="50" cy="50" r={radius} fill={stroke} fillOpacity={opacity} />);
  }
  return <g>{parts}</g>;
}

export function CrosshairPreview({ item }: { item: Style }) {
  const rotation = Math.abs(item.rotationDegrees) > 0.01 ? item.rotationDegrees : undefined;
  const outline = item.outlineEnabled && item.shape !== 'custom_grid';
  const outlineLine = item.thickness + 2 * (outline ? item.outlineThickness : 0);
  const outlineCircle = item.circleThickness + 2 * (outline ? item.outlineThickness : 0);
  const outlineDot = item.centerDotSize + 2 * (outline ? item.outlineThickness : 0);
  return (
    <div className="preview" aria-hidden="true">
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        <g transform={rotation ? `rotate(${rotation} 50 50)` : undefined}>
          {outline && <ShapeLayer item={item} stroke={item.outlineColor} opacity={item.outlineOpacity / 255} line={outlineLine} circle={outlineCircle} dot={outlineDot} />}
          <ShapeLayer item={item} stroke={item.color} opacity={item.opacity / 255} line={item.thickness} circle={item.circleThickness} dot={item.centerDotSize} />
        </g>
      </svg>
    </div>
  );
}

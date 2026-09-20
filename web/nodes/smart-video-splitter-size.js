export const MIN_WIDTH = 350;
export const MIN_HEIGHT = 700;

function finiteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
}

export function preserveNodeSize(currentSize, computedSize) {
    return [
        Math.max(MIN_WIDTH, finiteNumber(currentSize?.[0]), finiteNumber(computedSize?.[0])),
        Math.max(MIN_HEIGHT, finiteNumber(currentSize?.[1]), finiteNumber(computedSize?.[1])),
    ];
}

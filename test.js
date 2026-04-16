const W = 1920;
const I = 0.05;
const panRange = I * W * 0.5;
const tx = panRange; // progress = 0
const S = 1 + I;
const originX = 0; // top-left
// P' = S * (P + tx - O) + O
let p = 0; // left edge
let p_prime = S * (p + tx - originX) + originX;
console.log("Top-left origin, left edge at start:", p_prime);

const originX_right = W; // top-right
const tx_end = -panRange; // progress = 1
let p_right = W; // right edge
let p_right_prime = S * (p_right + tx_end - originX_right) + originX_right;
console.log("Top-right origin, right edge at end:", p_right_prime, "diff:", 1920 - p_right_prime);

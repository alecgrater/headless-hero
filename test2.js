const W = 1920; const I = 0.05; const S = 1 + I;
const maxTx = (W * I) / (2 * S);
console.log({ maxTx, panRangeCode: I * W * 0.5 });
// Check left edge when tx = maxTx
const p = 0; const O = W / 2;
const p_prime = S * (p + maxTx - O) + O;
console.log({ p_prime });

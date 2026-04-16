const W = 1920; const I = 0.05; const S = 1 + I;
const maxTx = (W * I) / 2 / S;

const progress = 0; // start
// if we want camera to pan LEFT, it must start looking RIGHT.
// looking RIGHT means image is shifted LEFT (tx < 0).
console.log("Pan Left, start tx should be negative:", -maxTx);
console.log("Pan Left, end tx should be positive:", maxTx);

// Code's pan_left:
const panRange = I * W * 0.5;
console.log("Code pan_left start:", panRange - 2 * panRange * 0);
console.log("Code pan_left end:", panRange - 2 * panRange * 1);

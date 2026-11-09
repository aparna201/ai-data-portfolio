% lstm_load_forecast.m
% LSTM version of the day-ahead cooling-load forecast (Deep Learning Toolbox).
% Reads the same CSV the Python scripts use (data/sample/cooling_load.csv).
%
% NOT RUN: written without access to MATLAB. Uses trainnet, so it needs R2023b or newer.
% The tested reference models (ridge, random forest, gradient boosting) are in Python.
%
% Idea: look at the last 72 hours of load and temperature, predict the load 24 hours
% after the last hour in that window. Same chronological split as the Python code.

T = readtable(fullfile('..', 'data', 'sample', 'cooling_load.csv'));
load_kw = T.load_kw;
temp    = T.temp_c;

lookback = 72;
horizon  = 24;

% scale with training-period statistics only, to avoid leaking the future
nTotal = height(T);
nTrain = floor(0.70 * nTotal);
nVal   = floor(0.15 * nTotal);
mu = mean(load_kw(1:nTrain));  sd = std(load_kw(1:nTrain));
mt = mean(temp(1:nTrain));     st = std(temp(1:nTrain));
X = [(load_kw - mu) / sd, (temp - mt) / st];

% build windows: each sample is [lookback x 2], the target is the load `horizon` hours later
nSamples = nTotal - lookback - horizon + 1;
seqs = cell(nSamples, 1);
targets = zeros(nSamples, 1);
for i = 1:nSamples
    seqs{i} = X(i:i+lookback-1, :)';                   % channels x time
    targets(i) = X(i+lookback-1+horizon, 1);
end

lastTrain = nTrain - lookback - horizon + 1;
lastVal   = nTrain + nVal - lookback - horizon + 1;
trainIdx = 1:lastTrain;
valIdx   = lastTrain+1:lastVal;
testIdx  = lastVal+1:nSamples;

layers = [
    sequenceInputLayer(2)
    lstmLayer(64, 'OutputMode', 'last')
    dropoutLayer(0.1)
    fullyConnectedLayer(1)];

options = trainingOptions('adam', ...
    'MaxEpochs', 40, 'MiniBatchSize', 64, 'InitialLearnRate', 1e-3, ...
    'ValidationData', {seqs(valIdx), targets(valIdx)}, ...
    'ValidationPatience', 6, 'Shuffle', 'every-epoch', 'Verbose', false);

net = trainnet(seqs(trainIdx), targets(trainIdx), layers, 'mse', options);

% score on the held-out test block, back in kW
pred = predict(net, seqs(testIdx)) * sd + mu;
actual = targets(testIdx) * sd + mu;
mae  = mean(abs(pred - actual));
mape = mean(abs(pred - actual) ./ actual) * 100;
fprintf('LSTM test MAE = %.1f kW, MAPE = %.2f%%\n', mae, mape);

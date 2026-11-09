% chiller_dispatch_fmincon.m
% MATLAB version of the dispatch optimiser: enumerate which chillers are ON,
% then split the demand across them with fmincon (Optimization Toolbox).
%
% NOT RUN: written without access to MATLAB. The tested reference is the Python
% version in chiller_opt/optimize.py. Check it against that on a few demands.
%
% Usage:  [loads, powerKW] = chiller_dispatch_fmincon(1200)

function [bestLoads, bestPower] = chiller_dispatch_fmincon(demandKW)

    % name        capacity  copMax  bestPLR  minPLR   (same made-up plant as the Python code)
    plant = [1000   6.0   0.80   0.20;
             1000   5.5   0.75   0.20;
              500   5.0   0.70   0.20];
    n = size(plant, 1);

    % electrical power of one chiller carrying `load` kW of cooling
    power = @(k, load) load ./ (plant(k,2) .* (1 - 1.5 .* (load ./ plant(k,1) - plant(k,3)).^2));

    bestPower = inf;
    bestLoads = zeros(1, n);
    opts = optimoptions('fmincon', 'Display', 'off', 'Algorithm', 'sqp');

    for mask = 1:(2^n - 1)
        on = find(bitget(mask, 1:n));
        lo = plant(on, 4)' .* plant(on, 1)';        % minimum stable load of each ON unit
        hi = plant(on, 1)';                         % capacity of each ON unit
        if demandKW < sum(lo) || demandKW > sum(hi)
            continue                                % this combination cannot serve the demand
        end

        total = @(x) sum(arrayfun(@(i) power(on(i), x(i)), 1:numel(on)));
        x0 = demandKW * hi / sum(hi);               % start from a split proportional to capacity
        Aeq = ones(1, numel(on));                   % loads must add up to the demand
        [x, fval, flag] = fmincon(total, x0, [], [], Aeq, demandKW, lo, hi, [], opts);

        if flag > 0 && fval < bestPower
            bestPower = fval;
            bestLoads = zeros(1, n);
            bestLoads(on) = x;
        end
    end

    if isinf(bestPower)
        error('No feasible dispatch for demand %.0f kW', demandKW);
    end
end

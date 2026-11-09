% chiller_dispatch_ga_pso.m
% The same dispatch problem solved with two metaheuristics, to compare against the
% gradient-based version in chiller_dispatch_fmincon.m:
%   * ga (genetic algorithm) with integer ON/OFF variables
%   * particleswarm on the load split, with the ON set fixed
%
% NOT RUN: written without access to MATLAB (needs Global Optimization Toolbox).
% Treat as a starting point and compare results with the Python reference.
%
% Usage:  compare_metaheuristics(1200)

function compare_metaheuristics(demandKW)
    cap   = [1000 1000 500];
    copMx = [6.0  5.5  5.0];
    best  = [0.80 0.75 0.70];
    minPL = 0.20;

    % decision vector z = [on1 on2 on3 load1 load2 load3]
    power = @(z) sum( z(1:3) .* z(4:6) ./ (copMx .* (1 - 1.5 .* (z(4:6) ./ cap - best).^2)) );
    % a unit that is OFF carries no load; a unit that is ON stays within its stable range
    nonlcon = @(z) deal([ z(4:6) - z(1:3) .* cap, z(1:3) .* minPL .* cap - z(4:6) ], []);

    lb = [0 0 0 0 0 0];
    ub = [1 1 1 cap];
    Aeq = [0 0 0 1 1 1];

    % --- genetic algorithm, integer ON/OFF ---
    gaOpts = optimoptions('ga', 'Display', 'off', 'PopulationSize', 100, 'MaxGenerations', 200);
    [zGA, pGA] = ga(power, 6, [], [], Aeq, demandKW, lb, ub, nonlcon, 1:3, gaOpts);

    % --- particle swarm on the load split, ON set taken from the GA result ---
    on = find(round(zGA(1:3)));
    fixedPower = @(x) sum( x ./ (copMx(on) .* (1 - 1.5 .* (x ./ cap(on) - best(on)).^2)) ) ...
                      + 1e6 * abs(sum(x) - demandKW);          % penalty keeps the balance
    psoOpts = optimoptions('particleswarm', 'Display', 'off', 'SwarmSize', 60);
    [xPSO, pPSO] = particleswarm(fixedPower, numel(on), minPL * cap(on), cap(on), psoOpts);

    fprintf('GA : units ON = %s, power = %.1f kW\n', mat2str(round(zGA(1:3))), pGA);
    fprintf('PSO: loads = %s, power = %.1f kW\n', mat2str(round(xPSO, 1)), pPSO);
end

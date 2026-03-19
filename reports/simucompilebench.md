# SimuCompileBench

- evaluated systems: 255
- passed systems: 255
- failed systems: 0
- tolerance: 1e-06

## Baseline Regression Check
- matches baseline: True

## Tier Summary
- tier1_verified: 216/216 (100.0%)
- tier2_structural: 28/28 (100.0%)
- tier3_adversarial: 11/11 (100.0%)

## Failure Categories
- graph_invalid: 1
- numerical_instability: 1
- parse_failure: 4
- symbolic_failure: 5

## Aggregate Metrics
- average RMSE: 1.359518253632065e-11
- median RMSE: 5.598815055041188e-12
- max RMSE: 6.235087113566107e-10
- average max abs error: 6.49362105612091e-11
- max abs error: 3.956256433568228e-09
- average robustness score: 1.0

## Complexity by Generated State Count
- 1 states: avg graph nodes=13.19047619047619, avg Simulink blocks=10.675, avg build time=1.833975288453803, avg sim time=0.18969564585422632
- 2 states: avg graph nodes=22.121951219512194, avg Simulink blocks=17.951219512195124, avg build time=1.5101156554897543, avg sim time=0.16080786480011827
- 3 states: avg graph nodes=31.135135135135137, avg Simulink blocks=26.0, avg build time=1.6052164301304523, avg sim time=0.16399262386462274
- 4 states: avg graph nodes=36.794871794871796, avg Simulink blocks=31.846153846153847, avg build time=1.649070518256989, avg sim time=0.15833397125765586
- 5 states: avg graph nodes=45.08108108108108, avg Simulink blocks=39.5945945945946, avg build time=1.7225259008685228, avg sim time=0.16867579503387614
- 6 states: avg graph nodes=51.44736842105263, avg Simulink blocks=45.71052631578947, avg build time=1.8312605042868342, avg sim time=0.20146295602745867
- 8 states: avg graph nodes=106.5, avg Simulink blocks=98.5, avg build time=9.382258375015226, avg sim time=0.5027628227690002
- 10 states: avg graph nodes=131.5, avg Simulink blocks=123.5, avg build time=3.5249073855229653, avg sim time=0.14479684349498712
- 12 states: avg graph nodes=156.25, avg Simulink blocks=148.25, avg build time=3.9844410942605464, avg sim time=0.1715408434974961

## System Results
### syn_s1_d1_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.2308234888418206e-12
- max_abs_error: 1.1851311598753966e-11
- robustness_score: None

### syn_s1_d1_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.84647145434705e-12
- max_abs_error: 1.1940899657947313e-11
- robustness_score: None

### syn_s1_d1_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.1334106771236824e-11
- max_abs_error: 3.050343311272741e-11
- robustness_score: None

### syn_s1_d1_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 6.584430376525043e-12
- max_abs_error: 1.889494116724677e-11
- robustness_score: None

### syn_s1_d1_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.096625646875348e-12
- max_abs_error: 1.651754427678398e-11
- robustness_score: None

### syn_s1_d1_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.4799620748532254e-11
- max_abs_error: 4.3322456733108083e-11
- robustness_score: None

### syn_s2_d1_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.538929218591408e-12
- max_abs_error: 1.471936461605594e-11
- robustness_score: None

### syn_s2_d1_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.7724990709274255e-12
- max_abs_error: 1.4273970894151944e-11
- robustness_score: None

### syn_s2_d1_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.2029083124028897e-11
- max_abs_error: 3.143360571833398e-11
- robustness_score: None

### syn_s2_d1_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.636084623632567e-10
- max_abs_error: 7.039729355007296e-10
- robustness_score: None

### syn_s2_d1_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.872135692224446e-12
- max_abs_error: 5.754556553494439e-12
- robustness_score: None

### syn_s2_d1_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.41803382827337e-12
- max_abs_error: 1.712779917895091e-11
- robustness_score: None

### syn_s3_d1_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.844924060224778e-12
- max_abs_error: 2.0042342785409062e-11
- robustness_score: None

### syn_s3_d1_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.01205506877626e-12
- max_abs_error: 1.744204780607106e-11
- robustness_score: None

### syn_s3_d1_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 8.83950779610307e-12
- max_abs_error: 2.4543506116359026e-11
- robustness_score: None

### syn_s3_d1_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.1232581298439501e-11
- max_abs_error: 2.766201157022863e-11
- robustness_score: None

### syn_s3_d1_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.1976336838893397e-12
- max_abs_error: 1.4993249697337063e-11
- robustness_score: None

### syn_s3_d1_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.943775246704493e-11
- max_abs_error: 7.890355036010988e-11
- robustness_score: None

### syn_s4_d1_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.0165186812977044e-12
- max_abs_error: 1.2293902007520785e-11
- robustness_score: None

### syn_s4_d1_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.623098578575276e-12
- max_abs_error: 1.2354638145861685e-11
- robustness_score: None

### syn_s4_d1_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 9.690909607740507e-12
- max_abs_error: 5.001912772861772e-11
- robustness_score: None

### syn_s4_d1_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.7471136479459414e-12
- max_abs_error: 1.5257219099229502e-11
- robustness_score: None

### syn_s4_d1_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.245362780006608e-12
- max_abs_error: 1.923777803725102e-11
- robustness_score: None

### syn_s4_d1_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.4678462906023406e-12
- max_abs_error: 1.627957491034948e-11
- robustness_score: None

### syn_s5_d1_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.107251302524034e-12
- max_abs_error: 1.779849184702087e-11
- robustness_score: None

### syn_s5_d1_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.296453504119198e-12
- max_abs_error: 1.7118396977711114e-11
- robustness_score: None

### syn_s5_d1_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.2012718365752637e-11
- max_abs_error: 5.56767965065319e-11
- robustness_score: None

### syn_s5_d1_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.752959941544218e-11
- max_abs_error: 7.470493668115807e-11
- robustness_score: None

### syn_s5_d1_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.4115140363947885e-12
- max_abs_error: 1.622103840137612e-11
- robustness_score: None

### syn_s5_d1_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.455489609279918e-12
- max_abs_error: 3.22338683522716e-11
- robustness_score: None

### syn_s6_d1_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.33095894751485e-12
- max_abs_error: 1.4003423420838601e-11
- robustness_score: None

### syn_s6_d1_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.9250993542185585e-12
- max_abs_error: 1.4208648146940561e-11
- robustness_score: None

### syn_s6_d1_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.2579388461806738e-11
- max_abs_error: 5.143288572817539e-11
- robustness_score: None

### syn_s6_d1_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 7.264610904226284e-12
- max_abs_error: 3.164410400380291e-11
- robustness_score: None

### syn_s6_d1_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.907181699237273e-12
- max_abs_error: 1.6588133644468428e-11
- robustness_score: None

### syn_s6_d1_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.049637836808224e-12
- max_abs_error: 2.2021176548925325e-11
- robustness_score: None

### syn_s1_d1_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.5155520869290946e-12
- max_abs_error: 1.147741623963583e-11
- robustness_score: None

### syn_s1_d1_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.372941009501912e-12
- max_abs_error: 1.221049650279582e-11
- robustness_score: None

### syn_s1_d1_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 3.514468301568928e-12
- max_abs_error: 1.2059554743704126e-11
- robustness_score: None

### syn_s1_d1_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.1338323545246201e-11
- max_abs_error: 2.3401391935351512e-11
- robustness_score: None

### syn_s1_d1_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 2.349071003836547e-11
- max_abs_error: 7.714212602039083e-11
- robustness_score: None

### syn_s1_d1_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.497975305668605e-11
- max_abs_error: 8.018963271183566e-11
- robustness_score: None

### syn_s2_d1_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.06802281767972e-12
- max_abs_error: 1.5309892242854062e-11
- robustness_score: None

### syn_s2_d1_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.22834737857744e-12
- max_abs_error: 1.5567658273596408e-11
- robustness_score: None

### syn_s2_d1_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.3817421338464373e-11
- max_abs_error: 4.287184496298835e-11
- robustness_score: None

### syn_s2_d1_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 9.574158346404846e-12
- max_abs_error: 2.3701138274212497e-11
- robustness_score: None

### syn_s2_d1_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.3877018261353876e-12
- max_abs_error: 1.6873447084009285e-11
- robustness_score: None

### syn_s2_d1_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.0475743851702665e-11
- max_abs_error: 1.0487855028884496e-10
- robustness_score: None

### syn_s3_d1_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.377348271410759e-12
- max_abs_error: 2.1012941386899797e-11
- robustness_score: None

### syn_s3_d1_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.521523346052134e-12
- max_abs_error: 1.580382352761589e-11
- robustness_score: None

### syn_s3_d1_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 9.14324414308688e-12
- max_abs_error: 4.444761225741445e-11
- robustness_score: None

### syn_s3_d1_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.399842497533085e-11
- max_abs_error: 5.468031583077959e-11
- robustness_score: None

### syn_s3_d1_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.887522065938346e-12
- max_abs_error: 1.4949950999376682e-11
- robustness_score: None

### syn_s3_d1_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.9091868154436987e-11
- max_abs_error: 3.2448460585143835e-10
- robustness_score: None

### syn_s4_d1_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.455275669271027e-12
- max_abs_error: 1.2628183221341516e-11
- robustness_score: None

### syn_s4_d1_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.0682971480590654e-12
- max_abs_error: 1.3253363684295749e-11
- robustness_score: None

### syn_s4_d1_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 6.640367989800488e-12
- max_abs_error: 3.227158817953324e-11
- robustness_score: None

### syn_s4_d1_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.243962105088098e-11
- max_abs_error: 6.497967441898567e-11
- robustness_score: None

### syn_s4_d1_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 8.17934745346422e-12
- max_abs_error: 3.915809343446597e-11
- robustness_score: None

### syn_s4_d1_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.8259448890508366e-11
- max_abs_error: 1.0560441410234489e-10
- robustness_score: None

### syn_s5_d1_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.5768011567815644e-12
- max_abs_error: 1.781280678514463e-11
- robustness_score: None

### syn_s5_d1_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.814188377069364e-12
- max_abs_error: 1.7490897619154566e-11
- robustness_score: None

### syn_s5_d1_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 7.8831329422782e-12
- max_abs_error: 4.754585614108464e-11
- robustness_score: None

### syn_s5_d1_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.987953223022121e-11
- max_abs_error: 6.932582286012234e-11
- robustness_score: None

### syn_s5_d1_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.089217477914581e-12
- max_abs_error: 2.269276433430889e-11
- robustness_score: None

### syn_s5_d1_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.9437851032662894e-11
- max_abs_error: 8.859808720007578e-11
- robustness_score: None

### syn_s6_d1_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.850348868313454e-12
- max_abs_error: 1.4319857799538482e-11
- robustness_score: None

### syn_s6_d1_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.365180708433511e-12
- max_abs_error: 1.337004118528995e-11
- robustness_score: None

### syn_s6_d1_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 6.346325332265563e-12
- max_abs_error: 4.2125442023532855e-11
- robustness_score: None

### syn_s6_d1_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.748980875048033e-12
- max_abs_error: 2.5992999419521823e-11
- robustness_score: None

### syn_s6_d1_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.1791032186950535e-12
- max_abs_error: 2.6803899377814133e-11
- robustness_score: None

### syn_s6_d1_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 9.319523750625755e-11
- max_abs_error: 7.326983186839442e-10
- robustness_score: None

### syn_s1_d2_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.231959368875358e-12
- max_abs_error: 1.1956123591172485e-11
- robustness_score: None

### syn_s1_d2_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.853484302797799e-12
- max_abs_error: 1.1318980475127915e-11
- robustness_score: None

### syn_s1_d2_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 7.515047510699079e-11
- max_abs_error: 1.899149726369842e-10
- robustness_score: None

### syn_s1_d2_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.6885411685218268e-11
- max_abs_error: 6.332373514439382e-11
- robustness_score: None

### syn_s1_d2_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.697644736796053e-12
- max_abs_error: 1.7506322780302952e-11
- robustness_score: None

### syn_s1_d2_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 5.991734602348143e-12
- max_abs_error: 2.4220805916463917e-11
- robustness_score: None

### syn_s2_d2_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.476935534713365e-12
- max_abs_error: 1.3920531394262525e-11
- robustness_score: None

### syn_s2_d2_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.6807767964439606e-12
- max_abs_error: 1.5084086757433113e-11
- robustness_score: None

### syn_s2_d2_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 2.5684696669961704e-11
- max_abs_error: 1.7513534372737283e-10
- robustness_score: None

### syn_s2_d2_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.476015056086933e-11
- max_abs_error: 4.13702266888194e-11
- robustness_score: None

### syn_s2_d2_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 2.1811775449857685e-12
- max_abs_error: 1.2328756071600111e-11
- robustness_score: None

### syn_s2_d2_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 7.674438675644308e-12
- max_abs_error: 2.2100571372973832e-11
- robustness_score: None

### syn_s3_d2_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.942852380619049e-12
- max_abs_error: 1.806571559015424e-11
- robustness_score: None

### syn_s3_d2_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.259019122705983e-12
- max_abs_error: 1.346791428380456e-11
- robustness_score: None

### syn_s3_d2_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 6.235087113566107e-10
- max_abs_error: 3.956256433568228e-09
- robustness_score: None

### syn_s3_d2_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 5.132217854086762e-12
- max_abs_error: 1.9778761961575242e-11
- robustness_score: None

### syn_s3_d2_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.5957760739153687e-12
- max_abs_error: 1.4970455430862728e-11
- robustness_score: None

### syn_s3_d2_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.5988683432295862e-11
- max_abs_error: 6.811781694260333e-11
- robustness_score: None

### syn_s4_d2_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.904192450299594e-12
- max_abs_error: 1.2726195097734205e-11
- robustness_score: None

### syn_s4_d2_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.6718587353262616e-12
- max_abs_error: 1.4658899094577293e-11
- robustness_score: None

### syn_s4_d2_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 8.253346255014417e-12
- max_abs_error: 3.8687331116449286e-11
- robustness_score: None

### syn_s4_d2_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 9.8558100465187e-12
- max_abs_error: 3.8100606003510507e-11
- robustness_score: None

### syn_s4_d2_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.3393520810539296e-12
- max_abs_error: 1.8488766073687657e-11
- robustness_score: None

### syn_s4_d2_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.955104915010818e-12
- max_abs_error: 2.0234303815813703e-11
- robustness_score: None

### syn_s5_d2_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.025550271995807e-12
- max_abs_error: 1.6264836699697582e-11
- robustness_score: None

### syn_s5_d2_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.250069309369596e-12
- max_abs_error: 2.0441398573822767e-11
- robustness_score: None

### syn_s5_d2_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 6.086484920857933e-12
- max_abs_error: 3.382964741671657e-11
- robustness_score: None

### syn_s5_d2_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.339835985986855e-12
- max_abs_error: 3.5280667276538225e-11
- robustness_score: None

### syn_s5_d2_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.848207798073301e-12
- max_abs_error: 1.6012947912091846e-11
- robustness_score: None

### syn_s5_d2_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 5.58775491217558e-12
- max_abs_error: 2.4079668814458444e-11
- robustness_score: None

### syn_s6_d2_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.209439779954136e-12
- max_abs_error: 1.41811909437628e-11
- robustness_score: None

### syn_s6_d2_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.938795089356667e-12
- max_abs_error: 1.4350118315853422e-11
- robustness_score: None

### syn_s6_d2_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.2349153362090324e-11
- max_abs_error: 5.890879450909381e-11
- robustness_score: None

### syn_s6_d2_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.0196113928861589e-11
- max_abs_error: 4.531486297310039e-11
- robustness_score: None

### syn_s6_d2_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.944681019470921e-12
- max_abs_error: 2.010470956381738e-11
- robustness_score: None

### syn_s6_d2_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 5.7333440682245085e-12
- max_abs_error: 3.106118140472347e-11
- robustness_score: None

### syn_s1_d2_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.035422133403595e-12
- max_abs_error: 1.2104352242747751e-11
- robustness_score: None

### syn_s1_d2_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.0232082390521767e-12
- max_abs_error: 1.097005819516994e-11
- robustness_score: None

### syn_s1_d2_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 5.758452689219391e-12
- max_abs_error: 1.220186451877936e-11
- robustness_score: None

### syn_s1_d2_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 5.991726128654598e-12
- max_abs_error: 1.2273661254003088e-11
- robustness_score: None

### syn_s1_d2_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.334258745984307e-11
- max_abs_error: 9.739964390576006e-11
- robustness_score: None

### syn_s1_d2_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.66182066954108e-11
- max_abs_error: 4.3290382389926663e-10
- robustness_score: None

### syn_s2_d2_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.9921113167827225e-12
- max_abs_error: 1.5649467832723474e-11
- robustness_score: None

### syn_s2_d2_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.058351040070271e-12
- max_abs_error: 1.4094940492537233e-11
- robustness_score: None

### syn_s2_d2_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 4.813972329447681e-12
- max_abs_error: 2.3247855029939757e-11
- robustness_score: None

### syn_s2_d2_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 5.7704885706664056e-11
- max_abs_error: 4.629394645405682e-10
- robustness_score: None

### syn_s2_d2_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 8.863071698665491e-12
- max_abs_error: 2.8562124887443474e-11
- robustness_score: None

### syn_s2_d2_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.67359841159353e-11
- max_abs_error: 2.61466071016514e-10
- robustness_score: None

### syn_s3_d2_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.1988203277371594e-12
- max_abs_error: 1.8451580541256618e-11
- robustness_score: None

### syn_s3_d2_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.596028278951237e-12
- max_abs_error: 1.4335525821973505e-11
- robustness_score: None

### syn_s3_d2_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 2.6025044229340336e-12
- max_abs_error: 1.5987836055053606e-11
- robustness_score: None

### syn_s3_d2_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.025092121170792e-11
- max_abs_error: 1.803968086022678e-10
- robustness_score: None

### syn_s3_d2_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.840148303213614e-12
- max_abs_error: 2.0022872249114698e-11
- robustness_score: None

### syn_s3_d2_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.684920449005803e-11
- max_abs_error: 3.5313182933371934e-10
- robustness_score: None

### syn_s4_d2_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.4181495143938125e-12
- max_abs_error: 1.3408205101761439e-11
- robustness_score: None

### syn_s4_d2_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.2299141639889977e-12
- max_abs_error: 1.6136120217780103e-11
- robustness_score: None

### syn_s4_d2_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.941803077699635e-11
- max_abs_error: 9.735207084915487e-11
- robustness_score: None

### syn_s4_d2_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.3867451450377655e-11
- max_abs_error: 4.069422576691295e-11
- robustness_score: None

### syn_s4_d2_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.14857251532648e-11
- max_abs_error: 5.8205829045476776e-11
- robustness_score: None

### syn_s4_d2_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.973571138889535e-11
- max_abs_error: 2.11174078224019e-10
- robustness_score: None

### syn_s5_d2_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.588993735142404e-12
- max_abs_error: 1.722558207184477e-11
- robustness_score: None

### syn_s5_d2_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.659615359085008e-12
- max_abs_error: 1.9529086681124852e-11
- robustness_score: None

### syn_s5_d2_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 3.2806994443241225e-12
- max_abs_error: 1.8904912357786685e-11
- robustness_score: None

### syn_s5_d2_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.118333527385544e-12
- max_abs_error: 4.559330690767638e-11
- robustness_score: None

### syn_s5_d2_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 8.999246623458048e-12
- max_abs_error: 3.384889590840601e-11
- robustness_score: None

### syn_s5_d2_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.2408266881216289e-11
- max_abs_error: 8.833767051186214e-11
- robustness_score: None

### syn_s6_d2_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.70751175793278e-12
- max_abs_error: 1.4903654699249813e-11
- robustness_score: None

### syn_s6_d2_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.3898422130851997e-12
- max_abs_error: 1.587706355277163e-11
- robustness_score: None

### syn_s6_d2_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 4.563985476468447e-12
- max_abs_error: 2.3533716642099023e-11
- robustness_score: None

### syn_s6_d2_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.580237809794086e-12
- max_abs_error: 4.879177617489461e-11
- robustness_score: None

### syn_s6_d2_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 8.066335519967245e-12
- max_abs_error: 3.785416424761934e-11
- robustness_score: None

### syn_s6_d2_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.387265884985928e-12
- max_abs_error: 4.3378522995851654e-11
- robustness_score: None

### syn_s1_d3_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.2330981397272516e-12
- max_abs_error: 1.167171914673304e-11
- robustness_score: None

### syn_s1_d3_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.8537409923216954e-12
- max_abs_error: 1.1940344546435e-11
- robustness_score: None

### syn_s1_d3_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 4.2513414488358366e-12
- max_abs_error: 1.2234976920488805e-11
- robustness_score: None

### syn_s1_d3_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.0591388460523082e-11
- max_abs_error: 3.4968944406799096e-11
- robustness_score: None

### syn_s1_d3_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.129864008074764e-12
- max_abs_error: 1.8989837480276606e-11
- robustness_score: None

### syn_s1_d3_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 7.890608957670556e-12
- max_abs_error: 2.0939500133820843e-11
- robustness_score: None

### syn_s2_d3_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.414089065885563e-12
- max_abs_error: 1.497177382070447e-11
- robustness_score: None

### syn_s2_d3_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.980428265147511e-12
- max_abs_error: 1.5286119592339276e-11
- robustness_score: None

### syn_s2_d3_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 4.143035880178591e-12
- max_abs_error: 1.9816558116669825e-11
- robustness_score: None

### syn_s2_d3_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.3783497566538448e-11
- max_abs_error: 3.552752536606363e-11
- robustness_score: None

### syn_s2_d3_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 2.2236010140541877e-12
- max_abs_error: 6.788722362038868e-12
- robustness_score: None

### syn_s2_d3_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.6810635919335912e-11
- max_abs_error: 6.805711549873195e-11
- robustness_score: None

### syn_s3_d3_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.8787910551723275e-12
- max_abs_error: 1.6886554654593766e-11
- robustness_score: None

### syn_s3_d3_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.170343668767836e-12
- max_abs_error: 1.7638654425944367e-11
- robustness_score: None

### syn_s3_d3_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.3210835828065133e-11
- max_abs_error: 4.705941192284513e-11
- robustness_score: None

### syn_s3_d3_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.127157196000592e-11
- max_abs_error: 6.167655275390871e-11
- robustness_score: None

### syn_s3_d3_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 2.097145526816172e-12
- max_abs_error: 6.176857636486233e-12
- robustness_score: None

### syn_s3_d3_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.8072745334558825e-12
- max_abs_error: 1.8471779661410892e-11
- robustness_score: None

### syn_s4_d3_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.810810305507336e-12
- max_abs_error: 1.2649485625626511e-11
- robustness_score: None

### syn_s4_d3_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 2.9854403332089174e-12
- max_abs_error: 1.254710224607436e-11
- robustness_score: None

### syn_s4_d3_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 8.402611272365109e-12
- max_abs_error: 3.939068515812494e-11
- robustness_score: None

### syn_s4_d3_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.2172386521322193e-11
- max_abs_error: 5.599359864660869e-11
- robustness_score: None

### syn_s4_d3_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 2.6034008526144227e-12
- max_abs_error: 7.456937844985134e-12
- robustness_score: None

### syn_s4_d3_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.961978328146726e-12
- max_abs_error: 2.2461282833674545e-11
- robustness_score: None

### syn_s5_d3_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.938963415449517e-12
- max_abs_error: 1.7358926795996155e-11
- robustness_score: None

### syn_s5_d3_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.7892127966383264e-12
- max_abs_error: 2.9612562402192566e-11
- robustness_score: None

### syn_s5_d3_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 2.3062111095706758e-11
- max_abs_error: 8.860778777375344e-11
- robustness_score: None

### syn_s5_d3_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 6.5065200328268884e-12
- max_abs_error: 2.086020245428699e-11
- robustness_score: None

### syn_s5_d3_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.404398443161114e-12
- max_abs_error: 2.1246129855434503e-11
- robustness_score: None

### syn_s5_d3_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.6252084858108235e-12
- max_abs_error: 1.1195717963818907e-11
- robustness_score: None

### syn_s6_d3_u0_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 4.108528620481354e-12
- max_abs_error: 1.4117526592194451e-11
- robustness_score: None

### syn_s6_d3_u0_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.319541589201766e-12
- max_abs_error: 1.3398650244855759e-11
- robustness_score: None

### syn_s6_d3_u0_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 2.471474446800361e-11
- max_abs_error: 1.3222362094111872e-10
- robustness_score: None

### syn_s6_d3_u0_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 6.818088996915987e-12
- max_abs_error: 3.388124503178602e-11
- robustness_score: None

### syn_s6_d3_u0_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 2.1010115361882283e-12
- max_abs_error: 7.941536317446207e-12
- robustness_score: None

### syn_s6_d3_u0_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.83251439327038e-12
- max_abs_error: 3.047076480022781e-11
- robustness_score: None

### syn_s1_d3_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.1771790428768213e-12
- max_abs_error: 1.1837225644129035e-11
- robustness_score: None

### syn_s1_d3_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.182738130805927e-12
- max_abs_error: 1.2348580491483574e-11
- robustness_score: None

### syn_s1_d3_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 1.36662187108208e-11
- max_abs_error: 3.800915138185701e-11
- robustness_score: None

### syn_s1_d3_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.2615790637618925e-12
- max_abs_error: 9.900927300243723e-12
- robustness_score: None

### syn_s1_d3_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.889940323021919e-11
- max_abs_error: 2.7915836309233555e-10
- robustness_score: None

### syn_s1_d3_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 9.678862420378731e-11
- max_abs_error: 4.5557002614771136e-10
- robustness_score: None

### syn_s2_d3_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.80155941946371e-12
- max_abs_error: 1.3897667738849151e-11
- robustness_score: None

### syn_s2_d3_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.3444717786159e-12
- max_abs_error: 1.601625776448401e-11
- robustness_score: None

### syn_s2_d3_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 2.9794864100614965e-11
- max_abs_error: 1.5280857135202552e-10
- robustness_score: None

### syn_s2_d3_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.096300759863536e-11
- max_abs_error: 2.388869657643511e-11
- robustness_score: None

### syn_s2_d3_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 9.009729351704517e-12
- max_abs_error: 2.728051118339181e-11
- robustness_score: None

### syn_s2_d3_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.0993005448313413e-11
- max_abs_error: 4.1278314100168245e-11
- robustness_score: None

### syn_s3_d3_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.871732149055356e-12
- max_abs_error: 1.7886692127433435e-11
- robustness_score: None

### syn_s3_d3_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.5906870791275464e-12
- max_abs_error: 2.006450561253814e-11
- robustness_score: None

### syn_s3_d3_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 3.9151804742651705e-12
- max_abs_error: 1.8426996040155075e-11
- robustness_score: None

### syn_s3_d3_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.818985828162257e-12
- max_abs_error: 1.7656459627701793e-11
- robustness_score: None

### syn_s3_d3_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.096110108056902e-12
- max_abs_error: 3.011613181058692e-11
- robustness_score: None

### syn_s3_d3_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 4.8159492239598664e-11
- max_abs_error: 2.208510041512568e-10
- robustness_score: None

### syn_s4_d3_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.2221277747396207e-12
- max_abs_error: 1.1850791181711173e-11
- robustness_score: None

### syn_s4_d3_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.688278625112021e-12
- max_abs_error: 1.37375666398043e-11
- robustness_score: None

### syn_s4_d3_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 2.0248006798965095e-11
- max_abs_error: 5.7979010481545856e-11
- robustness_score: None

### syn_s4_d3_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 5.6098751979067964e-12
- max_abs_error: 2.942199262001566e-11
- robustness_score: None

### syn_s4_d3_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.3433906605579684e-11
- max_abs_error: 7.711831173651262e-11
- robustness_score: None

### syn_s4_d3_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.1218290081753864e-11
- max_abs_error: 2.084222794351831e-10
- robustness_score: None

### syn_s5_d3_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.2702870555791653e-12
- max_abs_error: 1.710741270866123e-11
- robustness_score: None

### syn_s5_d3_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.635847979080629e-12
- max_abs_error: 2.2854718118026085e-11
- robustness_score: None

### syn_s5_d3_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 8.595733839411989e-12
- max_abs_error: 4.038860912380926e-11
- robustness_score: None

### syn_s5_d3_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 3.187737199636832e-11
- max_abs_error: 1.2391554449209252e-10
- robustness_score: None

### syn_s5_d3_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.013753458571118e-12
- max_abs_error: 2.5373952938778643e-11
- robustness_score: None

### syn_s5_d3_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 9.877042005104434e-12
- max_abs_error: 3.496200551289519e-11
- robustness_score: None

### syn_s6_d3_u1_f0
- tier: tier1_verified
- family: legacy::linear_first_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.3811348644717204e-12
- max_abs_error: 1.3015095945423383e-11
- robustness_score: None

### syn_s6_d3_u1_f1
- tier: tier1_verified
- family: legacy::linear_dense_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.813715211877951e-12
- max_abs_error: 1.2805180527042381e-11
- robustness_score: None

### syn_s6_d3_u1_f2
- tier: tier1_verified
- family: legacy::nonlinear_polynomial
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: False
- rmse: 3.0111726221674822e-12
- max_abs_error: 2.073489296927633e-11
- robustness_score: None

### syn_s6_d3_u1_f3
- tier: tier1_verified
- family: legacy::nonlinear_trigonometric
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.3824665267706832e-11
- max_abs_error: 9.090284081025857e-11
- robustness_score: None

### syn_s6_d3_u1_f4
- tier: tier1_verified
- family: legacy::linear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.762666887959601e-12
- max_abs_error: 2.8437141530446297e-11
- robustness_score: None

### syn_s6_d3_u1_f5
- tier: tier1_verified
- family: legacy::nonlinear_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 1.4347835825438869e-11
- max_abs_error: 6.111866568403457e-11
- robustness_score: None

### struct_dense_linear_8
- tier: tier2_structural
- family: scaled_dense_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.6315441024302555e-12
- max_abs_error: 8.970033049671144e-12
- robustness_score: 1.0

### struct_dense_linear_8_input
- tier: tier2_structural
- family: scaled_dense_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 9.795659543647059e-13
- max_abs_error: 8.966070941252013e-12
- robustness_score: 1.0

### struct_mixed_order_8
- tier: tier2_structural
- family: scaled_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.6487784521370315e-12
- max_abs_error: 9.8034113243722e-12
- robustness_score: 1.0

### struct_dense_linear_10
- tier: tier2_structural
- family: scaled_dense_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.5097639457255124e-12
- max_abs_error: 8.961630049153513e-12
- robustness_score: 1.0

### struct_dense_linear_10_input
- tier: tier2_structural
- family: scaled_dense_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 9.732608335589411e-13
- max_abs_error: 9.657719068911774e-12
- robustness_score: 1.0

### struct_mixed_order_10
- tier: tier2_structural
- family: scaled_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.610264867767496e-12
- max_abs_error: 1.0798836434441905e-11
- robustness_score: 1.0

### struct_dense_linear_12
- tier: tier2_structural
- family: scaled_dense_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.6637435860833843e-12
- max_abs_error: 9.12351791337862e-12
- robustness_score: 1.0

### struct_dense_linear_12_input
- tier: tier2_structural
- family: scaled_dense_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.067520734726924e-12
- max_abs_error: 9.382949278657904e-12
- robustness_score: 1.0

### struct_mixed_order_12
- tier: tier2_structural
- family: scaled_mixed_order
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.604485436957831e-12
- max_abs_error: 1.1543370805663228e-11
- robustness_score: 1.0

### struct_dense_nonlinear_8
- tier: tier2_structural
- family: scaled_dense_nonlinear
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.993472194415368e-12
- max_abs_error: 2.8902519266793547e-11
- robustness_score: 1.0

### struct_dense_nonlinear_10
- tier: tier2_structural
- family: scaled_dense_nonlinear
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.972171446056036e-12
- max_abs_error: 3.315756003097192e-11
- robustness_score: 1.0

### struct_dense_nonlinear_12
- tier: tier2_structural
- family: scaled_dense_nonlinear
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 8.993471269051223e-12
- max_abs_error: 2.8902519266793547e-11
- robustness_score: 1.0

### higher_order_3_linear
- tier: tier2_structural
- family: higher_order_scalar
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.181588009806653e-12
- max_abs_error: 1.5394088781484072e-11
- robustness_score: 1.0

### higher_order_4_linear
- tier: tier2_structural
- family: higher_order_scalar
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 6.481385357570352e-12
- max_abs_error: 1.8011238334114665e-11
- robustness_score: 1.0

### higher_order_5_linear
- tier: tier2_structural
- family: higher_order_scalar
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.385619539628571e-12
- max_abs_error: 8.475126850315817e-12
- robustness_score: 1.0

### higher_order_4_nonlinear
- tier: tier2_structural
- family: higher_order_scalar
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 6.875800068981042e-12
- max_abs_error: 1.939141208717743e-11
- robustness_score: 1.0

### higher_order_coupled_pair
- tier: tier2_structural
- family: higher_order_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.202428302911479e-12
- max_abs_error: 1.3761533579348395e-11
- robustness_score: 1.0

### higher_order_nonlinear_pair
- tier: tier2_structural
- family: higher_order_coupled
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 6.976433065283091e-12
- max_abs_error: 2.7021510029534568e-11
- robustness_score: 1.0

### controlled_feedback_pair
- tier: tier2_structural
- family: controlled_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.435195896766631e-11
- max_abs_error: 5.5957578848353506e-11
- robustness_score: 1.0

### controlled_cascade_triple
- tier: tier2_structural
- family: controlled_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 7.331430426026775e-12
- max_abs_error: 1.7064002988398386e-11
- robustness_score: 1.0

### controlled_quad_chain
- tier: tier2_structural
- family: controlled_linear
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.697493122206909e-11
- max_abs_error: 5.813766135176479e-11
- robustness_score: 1.0

### controlled_nonlinear_pair
- tier: tier2_structural
- family: controlled_nonlinear
- overall_pass: True
- benchmark_result: pass
- nonlinear: True
- trig: True
- rmse: 2.019839443867874e-11
- max_abs_error: 4.1902065150978274e-11
- robustness_score: 1.0

### mass_spring_chain_4
- tier: tier2_structural
- family: physical_mass_spring
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 1.7939361885601356e-11
- max_abs_error: 6.696323183452701e-11
- robustness_score: 1.0

### mass_spring_chain_5_damped
- tier: tier2_structural
- family: physical_mass_spring
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 9.875812023461985e-12
- max_abs_error: 3.7011707500894664e-11
- robustness_score: 1.0

### mass_spring_chain_6_damped
- tier: tier2_structural
- family: physical_mass_spring
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 8.848482343542443e-12
- max_abs_error: 4.6711395168541614e-11
- robustness_score: 1.0

### rc_ladder_4
- tier: tier2_structural
- family: physical_rc_ladder
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 3.792158499267354e-12
- max_abs_error: 1.1802170352126495e-11
- robustness_score: 1.0

### rc_ladder_6
- tier: tier2_structural
- family: physical_rc_ladder
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 5.960292182504629e-12
- max_abs_error: 2.146184618911917e-11
- robustness_score: 1.0

### rlc_pair
- tier: tier2_structural
- family: physical_rlc
- overall_pass: True
- benchmark_result: pass
- nonlinear: False
- trig: False
- rmse: 7.221450205779986e-12
- max_abs_error: 1.63593444346688e-11
- robustness_score: 1.0

### hybrid_piecewise_cases
- tier: tier3_adversarial
- family: hybrid_unsupported
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: True
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: parse_failure
- failure_stage: parse
- failure_reason: Unsupported LaTeX command '\begin' at position 8.

### hybrid_saturation
- tier: tier3_adversarial
- family: hybrid_unsupported
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: True
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: parse_failure
- failure_stage: parse
- failure_reason: Unsupported LaTeX command '\operatorname' at position 8.

### hybrid_switching
- tier: tier3_adversarial
- family: hybrid_unsupported
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: True
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: parse_failure
- failure_stage: parse
- failure_reason: Unsupported LaTeX command '\max' at position 8.

### hybrid_sign_logic
- tier: tier3_adversarial
- family: hybrid_unsupported
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: True
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: parse_failure
- failure_stage: parse
- failure_reason: Unsupported LaTeX command '\mathrm' at position 8.

### adversarial_dae
- tier: tier3_adversarial
- family: symbolic_failure
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: False
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: symbolic_failure
- failure_stage: solve
- failure_reason: Equation 0 does not contain a highest-order derivative target; algebraic/DAE-like constraints are unsupported.

### adversarial_implicit_derivative
- tier: tier3_adversarial
- family: symbolic_failure
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: True
- trig: True
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: symbolic_failure
- failure_stage: solve
- failure_reason: Failed to isolate highest-order derivatives; implicit nonlinear derivative coupling is unsupported.

### adversarial_ambiguous_forcing
- tier: tier3_adversarial
- family: symbolic_failure
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: False
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: symbolic_failure
- failure_stage: state_extraction
- failure_reason: Ambiguous external-symbol classification encountered in pure forcing terms: a*z -> a, z

### adversarial_duplicate_derivative
- tier: tier3_adversarial
- family: symbolic_failure
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: False
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: symbolic_failure
- failure_stage: solve
- failure_reason: Overdetermined or inconsistent system: no deterministic solution for highest-order derivatives.

### adversarial_overdetermined_pair
- tier: tier3_adversarial
- family: symbolic_failure
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: False
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: symbolic_failure
- failure_stage: solve
- failure_reason: Overdetermined or inconsistent system: no deterministic solution for highest-order derivatives.

### adversarial_graph_fault
- tier: tier3_adversarial
- family: graph_fault_injection
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: False
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: graph_invalid
- failure_stage: graph_validation
- failure_reason: Graph node 'expr_0002' depends on missing node 'symbol_u'.

### adversarial_numerical_blowup
- tier: tier3_adversarial
- family: numerical_instability
- overall_pass: True
- benchmark_result: expected_failure_observed
- nonlinear: True
- trig: False
- rmse: None
- max_abs_error: None
- robustness_score: None
- failure_category: numerical_instability
- failure_stage: ode_simulation
- failure_reason: ODE simulation failed: Required step size is less than spacing between numbers.

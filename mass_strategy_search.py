"""
МАСОВО търсене на стратегии (03.11, по изрична молба: "има ли как да
направиш бот който да тества над 10000 trading стратегии без значение
часа просто да е за всеки ден добър win rate ... дай ми топ 10
стратегии"): вместо да добавяме по 2-3 "ръчни" стратегии на кръг както
във strategy_backtest.py досега (26 стратегии общо след 9 кръга), този
скрипт генерира ПАРАМЕТРИЗИРАНИ варианти на индикаторни "семейства"
(382 единични варианта след кръг 13 - виж по-долу), плюс всички двойки от
тях (до ~72 771 комбинации), на 5 различни "изходи" (exit) - над 360 000
стратегия×изход комбинации общо, т.е. МНОГО над поисканите 10 000.

КРЪГ 2 (03.11, по изрична молба "давай нови други стратегии ... целта ми
е да намира penny stocks от които да излизам на 10 процента печалба и
повече"): два вида промяна.
  (а) 9 НОВИ, механично различни семейства индикатори (27 нови варианта,
      166 единични общо) - нарочно от съвсем различни "училища" на
      техническия анализ, по същата логика както кръговете 6-9 в
      strategy_backtest.py (ADX/DMI, MACD, stochastic, OBV, candlestick
      форми, Elder's Force Index, Fibonacci ретрейсмънт, higher-low база,
      volatility contraction) - вместо пак да препараметризираме
      Donchian/ROC/RSI от кръг 1.
  (б) НОВА целева метрика покрай стандартния win_rate: вместо само "дали
      доходността е положителна", сега всеки сигнал се тества и с
      РЕАЛИСТИЧНА "take-profit/stop-loss" симулация -
      _simulate_target_stop_return() - купуваш на close(i), държиш до
      ПЪРВОТО от трите: (1) high докосва +--target-pct% (по подразбиране
      +10%) -> излизаш на печалба; (2) low докосва ---stop-pct% (по
      подразбиране -15%) -> излизаш на загуба; (3) никое от двете до край
      на хоризонта -> излизаш на close(i+h). `hit_target10pct_{h}d_%` =
      % от сигналите, при които РЕАЛНО си излязъл на +10% или повече -
      точно въпросът на потребителя "колко често намирам penny stock, от
      който излизам на 10%+", не абстрактен win rate. Класирането по
      подразбиране (--rank-by target_hit) сега сортира по ТАЗИ метрика,
      не по стария win_rate_{exit}_% (виж --rank-by по-долу, за да се
      върнеш към стария начин на класиране).

РЕЗУЛТАТ от 3-прозорец валидация на кръг 1+2 (03.11, ЗАПАЗЕНО по изрична
молба "запази я"): от ВСИЧКИ единични и комбинирани стратегии, тествани
през двата кръга, само ЕДНА бие random_baseline във ВСИЧКИ 3 прозореца
(--days 250 / --offset-days 250 / --offset-days 500), по ДВЕ различни
метрики:

    pullback_w40_0.2_0.4+volspike_w20_v2.0
    = цена дръпнала се 20-40% от 40-дневен връх (pullback_w40_0.2_0.4),
      ПОСЛЕ обемен скок >=2x 20-дневния среден обем (volspike_w20_v2.0)

  win_rate_close_5d_%:        42.0% / 66.7% / 50.0%  (baseline: 32.4% / 49.6% / 42.3%)
  hit_target_10pct_close_5d_%: 50.0% / 63.9% / 44.1%  (baseline: 29.4% / 38.6% / 29.2%)
  avg_ret_targetsim_close_5d_%: +0.11% / +3.79% / +1.04%
  stopped_out_close_5d_% (стига -15% преди +10%): 30.0% / 13.9% / 17.6%

За сравнение, ЖИВИЯТ Donchian сигнал на бота (`channel_period=20,
confirm_vol_mult=1.5` = `donch_h_w20_v1.5` в тази номенклатура) НЕ показва
стабилно предимство в СЪЩИТЕ 3 прозореца - win_rate 36.9%/44.5%/39.4%
срещу същия baseline (под/около него в 2 от 3), hit_target_10pct
33.3%/45.3%/31.8% с ОТРИЦАТЕЛНА средна симулирана доходност в 2 от 3
прозореца. Пазим тази находка тук като бенчмарк за бъдещи кръгове - ВСЯКА
нова стратегия/комбинация от кръговете по-долу трябва да се сравнява
и с тази, не само с random_baseline.

КРЪГ 3 (03.11, по молба "дай още стратегии"): 9 ОЩЕ нови механично
различни семейства (23 нови варианта, 189 единични общо, ако е наличен
SPY бенчмарк - виж --benchmark): Keltner Channel (ATR-базиран канал,
различен от Bollinger който е std-базиран), CCI oversold завой,
Williams %R oversold завой, Chaikin Money Flow (обемно-претеглена
accumulation/distribution, различна формула от OBV/A-D), VWAP reclaim
(цена пресича кумулативната обемно-претеглена средна цена), Parabolic
SAR flip (Wilder, ЕДИНСТВЕНОТО тук stateful/итеративно изчисление, не
rolling прозорец), relative strength vs SPY (ЕДИНСТВЕНОТО тук ОТНОСИТЕЛНО
измерение - бие ли пазара, не само расте ли absolute), volume climax
reversal (капитулационно дъно - голям ОБЕМЕН скок на ЧЕРВЕН ден, после
зелено затваряне - различно от volspike, който гледа ЗЕЛЕНИ дни), и
doji-after-breakout (свещна формация за нерешителност + пробив).

РЕЗУЛТАТ от кръг 3 (03.11, ЗАПАЗЕНО): новото VWAP семейство роди ВТОРИ
потвърден кандидат, оцелял във ВСИЧКИ 3 прозореца - `pullback_w20_0.1_0.3
+vwap_reclaim_w30` (дръпване 10-30% от 20-дневен връх + пресичане на VWAP
нагоре). hit_target_10pct_close_5d_%: 63.2% / 64.3% / 48.4% (baseline:
29.4% / 38.6% / 29.2%, edge +33.8/+25.7/+19.2пп) - по тази метрика ПО-ДОБЪР
и по-последователен от референтната находка от кръг 1+2
(pullback_w40_0.2_0.4+volspike_w20_v2.0, edge +20.6/+25.3/+14.9пп), с
по-нисък stopped_out риск. И двамата сега са "бенчмарк" кандидати - всяка
нова находка по-долу се сравнява и с тях.

КРЪГ 4 (03.11, по молба "дай още ама повече стратегии всякакви давай"):
10 ОЩЕ нови механично различни семейства (20 нови варианта, 209 единични
общо): Aroon нагоре/надолу (МЕРИ ВРЕМЕ от последния връх/дъно, не ниво на
цена/индикатор), TRIX (троен EMA-изгладен моментум), MFI (обемно-претеглен
RSI), PVT (кумулативен обем претеглен с % промяна, различно от OBV което
тегли само знака), ATR разширение пробив (волатилност РАСТЕ - обратното на
Bollinger squeeze, което гледа свиване), hammer и three-white-soldiers
(2 НОВИ свещни формации), N-дневно дъно отскок (контрариан БЕЗ изискване
за обем, за разлика от climax reversal), gap-down recovery (reversal,
огледален на gap-up-hold continuation), и Elder Ray Bull Power.

РЕЗУЛТАТ от кръг 4 (03.11, финално от 3-прозорец валидация): И ДВАТА
потвърдени кандидата от кръг 1-3 устояха и в трети прозорец (--offset-days
500) - pullback_w40_0.2_0.4+volspike_w20_v2.0 (win_rate 50.0%, hit_target
44.1%) и pullback_w20_0.1_0.3+vwap_reclaim_w30 (win_rate 45.2%, hit_target
48.4%), двата над baseline (win_rate 42.3%, hit_target 29.2%). Живият
Donchian сигнал на бота (donch_h_w20_v1.5) пак под/около baseline
(win_rate 39.4%, hit_target 31.8%, avg_ret -0.88%) - потвърдено окончателно
няма edge. НИКОЯ от 20-те нови кръг-4 единични/комбинации не издържа
всичките 3 прозореца - топ 10 на всеки прозорец поотделно е различен набор
(класически multiple-testing шум, виж честна бележка #1), включително
кандидатът bullpower_p21+obv_lead_w20 (силен само в прозорец 2, отпада в 1
и 3). Затова кръг 4 не donesе трети survivor - бенчмарк остава same 2.

КРЪГ 5 (03.11, по молба "ОЩЕ" след кръг 4): 10 ОЩЕ нови механично различни
семейства (20 нови варианта, 229 единични общо): Chande Momentum Oscillator
(CMO - подобен дух на RSI, но СУРОВА rolling сума на gain/loss, не Wilder
EMA като RSI), Ultimate Oscillator (комбинира 3 отделни хоризонта
buying-pressure/true-range в ЕДНА метрика - никое досегашно семейство не
смесва 3 периода наведнъж), Chaikin Oscillator (EMA3-EMA10 разлика ВЪРХУ
кумулативната Accumulation/Distribution линия - различно от CMF #23, което
е проста сума-съотношение без EMA), класически floor-trader Pivot Point
пробив над R1/R2 (ФИКСИРАНА геометрична формула от предишния бар, не
rolling прозорец), NR7/NR4 ("narrowest range" пробив - конкретен ден с
НАЙ-тесен диапазон от N, различно от three-bar-tight #16, което гледа само
3 последователни свиващи се дни), inside-bar пробив (класическа ценова
ФОРМА - днешният бар изцяло в снощния диапазон, после пробив над него),
linear-regression slope обрат (НАКЛОН на най-малки квадрати през rolling
прозорец обръща от <=0 към >0 - различна математика от MA кросоувър #8,
който сравнява ДВЕ нива, не наклон), RSI "бичи дивергенция" (цената е
близо до N-дневното дъно, НО RSI е ясно НАД своето собствено N-дневно дъно
- ПЪРВОТО тук семейство, което сравнява относителен екстремум на
ИНДИКАТОР към самия СЕБЕ СИ, не към бенчмарк като relstrength #26),
Supertrend бичи flip (ВТОРОТО stateful/итеративно изчисление тук покрай
Parabolic SAR #25 - ATR-базирани ленти с собствена state-машина, различна
формула от Keltner #20, който е статичен EMA+k*ATR канал без state), и
Awesome Oscillator (Bill Williams - SMA5 МИНУС SMA34 на (high+low)/2,
нулева линия + "ускорение" вариант).

РЕЗУЛТАТ от кръг 5 (03.11, финално): И двата потвърдени survivors устояха
отново във всичките 3 прозореца (числата съвпадат точно с кръг 1-4). НИКОЯ
от 20-те нови кръг-5 единични/комбинации не издържа - кандидатите
cmo_p9+pullback_w40_0.3_0.5 (силен само в прозорец 2) и
awesome_accel+roc_n10_t0.15 (силен само в прозорец 3) паднаха в другите
два прозореца всеки път - пак класически multiple-testing шум.

КРЪГ 6 (03.11, по молба "дай други" след кръг 5): 10 ОЩЕ нови механично
различни семейства (20 нови варианта, 249 единични общо): Donchian
MIDLINE пробив (различна точка на пробив от donch_h/donch_c - средата на
канала, не върха/затварянето), VWMA кросоувър (обемно-претеглени средни,
различни от простата SMA в macross), ROC "ускорение" (втора производна на
моментума), обемен осцилатор (чисто обемно измерение, без кумулативна
посока като OBV/PVT), Morning star (3-дневна свещна реверсал формация),
Donchian "width squeeze" пробив (ниска волатилност ПО ШИРИНА на канала,
различна база от Bollinger/ATR), EMA кросоувър (различно тегло от SMA
macross), OBV "бичи дивергенция" (аналогично на RSI дивергенция #46, но с
обемен инструмент), Keltner MIDLINE пробив (централна EMA, не горната
лента), и Acceleration Bands (Price Headley волатилност-разширяваща
формула).

РЕЗУЛТАТ от кръг 6 (03.11, ВАЖНО - ПЪРВО предупредително знаме): в
прозорец 1 и особено прозорец 3 на кръг 6, ДВАТА потвърдени survivors от
кръг 1-5 показаха ЗНАЧИМО по-слаби числа от историческите - в прозорец 3
за ПЪРВИ ПЪТ паднаха ПОД random_baseline по win_rate (pullback_w40_0.2_0.4
+volspike_w20_v2.0: 40.5% срещу baseline 43.1%; pullback_w20_0.1_0.3
+vwap_reclaim_w30: 33.3% срещу baseline 43.1%, avg_ret_targetsim стана
ОТРИЦАТЕЛЕН за втория -0.46%). hit_target_10pct остана над baseline и в
двата (+11.2пп/+12.4пп), но доверието в тях вече не е толкова сигурно,
колкото в кръг 1-5. Вероятна причина: universe.get_universe() е "жив" -
броят единични стратегии с достатъчно сигнали падна от 227 (прозорец 1) на
204 (прозорец 3) в СЪЩИЯ кръг, т.е. самият universe/данни се менят между
изпълненията, не само индикаторите. Никоя нова кръг-6 единична/комбинация
не издържа и в трите прозореца (morningstar+roc, cci_p20+morningstar,
cci_p20+pullback, nr4_breakout+volspike - всички паднаха след първия
прозорец, в който се появиха).

КРЪГ 7 (03.11, по изрична молба "дай напълно други стратегии различни от
тези"): 10 НАПЪЛНО различни семейства извън чистата техническа-индикаторна
"школа" на кръговете 1-6 (20 нови варианта, 269 единични общо): календарни
ефекти - ден-от-седмицата и начало/край на месеца (ЕДИНСТВЕНИТЕ тук
семейства без ВСЯКАКВА цена/обем, само датата), статистическо z-score
mean-reversion (разстояние в СТАНДАРТНИ ОТКЛОНЕНИЯ, не bounded оскилатор),
"accumulation" серия (поредни дни със затваряне в горния край на дневния
диапазон), цена-обем Pearson КОРЕЛАЦИЯ (не тегло на знак/величина като
OBV/PVT/CMF), регресионен тренд-канал (OLS права като "котва", не moving
average), "anchored" VWAP с ДИНАМИЧЕН swing-low анкер (не фиксиран rolling
прозорец), психологически "кръгли числа" пробив (нулева статистика),
Volatility Contraction Pattern (3 свиващи се "крака", Minervini стил), и
"Stage 2" дълго-прозоречна база + тих обем пробив (Weinstein стил).

КРЪГ 8 (04.11, по молба "давай още стратегии"): 9 НОВИ семейства (18 нови
варианта, 287 единични общо). ЧЕСТНА бележка: 3 идеи, обмислени първо за
този кръг - TTM Squeeze, Ichimoku Kijun cross, "Key reversal day" -
НАРОЧНО НЕ бяха добавени тук, защото вече СА тествани (под същите имена)
в ОТДЕЛНИЯ по-стар инструмент strategy_backtest.py/strategies.py - за
ichimoku_kijun_cross там изрично е записано, че излиза ПО-ЗЛЕ от random
extra-извадков (виж бележката по-горе при "ЗАЩО ВЕКТОРИЗИРАНО"); би било
безсмислено дублиране да ги "преоткриваме" тук като нови. Вместо тях:
Chandelier Exit бичи flip (ЧЕТВЪРТОТО stateful/итеративно изчисление тук,
покрай PSAR/Supertrend/Anchored VWAP - стоп-линия, анкерирана към rolling
highest-high/lowest-low, не към (H+L)/2 всеки ден като Supertrend), NVI
(Negative Volume Index) нов връх (кумулативен индекс, който се обновява
САМО в дни с ПО-НИСЪК обем от вчера - обратна логика на OBV/PVT), Coppock
Curve нулева линия (сума от 2 ROC, изгладена с ЛИНЕЙНО-претеглена MA, не
EMA като MACD/TRIX), Bollinger %B отскок от ДОЛНАТА лента (различна точка
на пробив от bbsqueeze/donchsqueeze, които гледат ГОРНАТА лента след
squeeze), Bollinger Band "walk" (N поредни затваряния НАД горната лента -
continuation ЧРЕЗ брой дни, не единичен кросоувър), Williams Alligator
(3 ИЗМЕСТЕНИ/изгладени средни - jaw/teeth/lips), сезонен "turn-of-year"/
January effect прозорец (разширява календарната логика от кръг 7 към
годишен хоризонт), предпразничен/следпразничен drift (РЕАЛЕН US federal
holiday календар, не аритметика на датата), и Stochastic RSI (Stochastic
формулата, приложена към САМИЯ RSI, не към цената).

РЕЗУЛТАТ от 3-прозорец валидация на кръг 8 (04.11): от 18-те нови варианта,
само `bbwalk_n3` (3 поредни затваряния НАД горната Bollinger лента) бие и
random_baseline, и живия Donchian сигнал във ВСИЧКИТЕ 3 прозореца по
win_rate_close_5d_% (47.6%/57.5%/55.6% срещу Donchian 33.8%/43.4%/42.9% -
стабилен марж +12.7 до +14.1пп всеки прозорец, на 15-21 различни тикера на
прозорец). ЧЕСТНА бележка: по avg_ret_targetsim_close_5d_% е леко ПОД
Donchian в прозорец 1 (-1.45% срещу -1.42%) - не е перфектен по ВСЯКА
метрика, само по win_rate категорично. `nvi_newhigh_w40` също бие baseline
в 3/3, но с много по-скромен марж (+0.2 до +9.2пп). Останалите 16 варианта
от кръг 8 не издържаха - нестабилни между прозорците.

КРЪГ 9 (04.11, по молба "продължаваме"): 8 НОВИ семейства (16 нови
варианта, 303 единични общо), проверени предварително срещу strategies.py
каталога, за да не се дублира грешката от кръг 8 (TTM Squeeze/Ichimoku/
Key-reversal бяха вече тествани там). Williams Fractal пробив (5-бар/3-бар
геометрична swing-high ФОРМАЦИЯ, различна от NR7/VCP), VWAP Bands пробив
(ленти анкерирани към VWAP, не SMA/EMA), относителен обем ПЕРЦЕНТИЛЕН ранг
(устойчива на outlier-и статистика, различна от volspike/volosc), Ehlers
Fisher Transform обрат (нелинеен логаритмичен трансформ), Guppy Multiple
Moving Average "ribbon" кросоувър (СРЕДНО от 6 EMA срещу СРЕДНО от други 6
EMA, не 2-EMA кросоувър), Relative Vigor Index (тяло/диапазон отношение,
различно от Force Index/Bull Power), McGinley Dynamic кросоувър (ПЕТОТО
stateful изчисление тук - единствената АДАПТИВНА-по-скорост средна), и
Percentage Price Oscillator (MACD конструкция, но МАЩАБНО-независима, %
вместо $ разлика).

РЕЗУЛТАТ от 3-прозорец валидация на кръг 9 (04.11): НИТО ЕДИН от 16-те нови
варианта не издържа стабилно и в трите прозореца - класически шум профил
(силни в прозорец 2-3, слаби в прозорец 1, или обратно). `bbwalk_n3` (кръг
8) се ПРЕПОТВЪРДИ на тези 2 допълнителни прозореца (60.0%/51.2% срещу
baseline 48.6%/41.7%) - вече 5 отделни изпълнения показват същия стабилен
марж.

КРЪГ 10 (04.11, по молба "10"): 8 НОВИ семейства (16 нови варианта, 319
единични общо), пак проверени срещу strategies.py каталога. Vortex
Indicator (VI+/VI- - абсолютно разстояние high/low спрямо противоположната
предишна цена, различно от ADX/DMI знак-базирана конструкция), Mass Index
"reversal bulge" (Dorsey/Bulkowski - двойно EMA-изгладено съотношение
диапазон/изгладен-диапазон, сумирано), Ease of Movement (комбинира
промяна в midpoint С обема по "лекота на движение" принцип, различно от
OBV/PVT/CMF/MFI/NVI), True Strength Index (ДВОЙНО EMA-изгладена
разлика/абсолютна-разлика), Detrended Price Oscillator (МИНАЛА цена
срещу ТЕКУЩА средна - премахва тренда), OBV Oscillator (OBV пресича
собствената си средна - MA-кросоувър механика върху обемен индикатор),
Pivot Point ПОДКРЕПА отскок (огледално на pivot_r1/r2 от кръг 5 - reversal
вместо continuation), и Chande Forecast Oscillator (% отклонение от OLS
регресионна прогноза, преизползва regchannel #54 с k=0).

КРЪГ 11 (04.11, по изрична молба "напълно нови 25 стратегии"): 12 НОВИ
семейства (25 нови варианта, 344 единични общо), пак проверени срещу
strategies.py каталога ПРЕДИ писане на код - Bullish Harami беше нарочно
ОТХВЪРЛЕНА (концептуално твърде близка до вече тествания three_inside_up),
Elder Ray Bull Power и A-D Line кросоувър НЕ бяха преоткривани (вече тук
като bullpower_p{p} #38 и adline_ema_f/s от по-ранни кръгове). Hull
Moving Average (анти-lag WMA конструкция), Volume Zone Oscillator
(баундиран обемно-подписан осцилатор, различен от OBV/PVT/CMF/MFI),
Keltner ДОЛНА лента отскок (огледално на Keltner #20), Ulcer Index
нисък-риск режим + пробив (drawdown-базирана волатилност, не ден-за-ден
размах), gap-up "клъстериране" (честота, не единично събитие като
gap_g_h #6), Qstick (rolling среден "дух" на тялото), "растящ" Donchian
канал (тренд на САМАТА лента, не обем/ниво), rolling skewness обрат
(трети статистически момент), Internal Bar Strength екстремум отскок,
"дълбоко" дъно отскок на 100/150-дневен хоризонт (огледално на
stage2 #58), rolling Beta "скок" спрямо SPY (статистическа чувствителност,
различна от relstrength #26), и rolling "Sharpe-подобно" съотношение обрат
(риск-коригиран моментум).

РЕЗУЛТАТ от 3-прозорец валидация на кръг 11 (04.11): НАЙ-ДОБРИЯТ кръг от
кръг 8 насам - ТРИ нови кандидата издържаха и трите прозореца по
win_rate_close_5d_% (бият и donch_h_w20_v1.5, и random_baseline във
ВСЕКИ прозорец): `ulcerlowbreak_n14` (45.5%/49.6%/47.1%, ЕДИНСТВЕНИЯТ с
положителна avg_ret_targetsim в 2 от 3 прозореца: +0.28%/+0.32%/-0.85%),
`ulcerlowbreak_n20` (48.2%/49.2%/49.3% - най-стабилен по win_rate,
разлика само 1пп между прозорците), и `donchrising_w40`
(43.4%/52.0%/43.4%, но avg_ret предимно отрицателна). ЧЕСТНА бележка:
НИТО ЕДИН от трите бие установения жив бенчмарк
pullback_w20_0.1_0.3+vwap_reclaim_w30 по hit_target/avg_ret метриките
(то остава по-прецизно, но с 2-7x по-малко сигнали). `keltnerlower_p20_k2.0`
и `deeplow_bounce_w100/w150` изглеждаха отлично в прозорци 2-3, но
КАТАСТРОФАЛНО зле в прозорец 1 (23-34% win, до -5% avg_ret) - класически
multiple-testing шум, отхвърлени. `gapcluster` семейството отпадна почти
навсякъде заради твърде малко сигнали (прагът --min-signals/--min-symbols).

КРЪГ 12 (04.11, по молба "продължаваме още стратегии давай"): 10 НОВИ
механично различни семейства (20 нови варианта, 364 единични общо),
проверени предварително срещу strategies.py каталога - Darvas Box беше
НАРОЧНО пропуснат (вече тестван там, "леко по-добър от random" - твърде
слабо за преоткриване), Aroon кросоувър НЕ бе преоткриван (вече тук като
aroon_p{p} #29). KAMA (Kaufman Adaptive MA, ШЕСТОТО stateful изчисление
тук - скорост според Efficiency Ratio, не според съотношение цена/предишна
стойност като McGinley #74), Choppiness Index трендиращ режим + пробив
(логаритмична trend-quality метрика, различна от Ulcer #87/ADX #14), TEMA
(тройна EMA, анти-lag конструкция различна от Hull #84), Klinger Volume
Oscillator (ОПРОСТЕНО, честно документирано - обем тежен по дневния
размах, не по знак като OBV или позиция-в-диапазона като CMF/MFI), Balance
of Power изгладен (МАЩАБНО-НЕЗАВИСИМА версия на Qstick #89), Camarilla
pivot (различна геометрия от floor-trader pivot #42), "Three Outside Up"
(3-свещна ENGULFING-базирана формация - РАЗЛИЧНА база от HARAMI-базирания
three_inside_up в strategies.py), EMA "ribbon" строга подредба (N средни
наведнъж, различно от GMMA #72 2-групово сравнение), Weighted Close
кросоувър (теглена типична цена вместо чист close), и MA "ускорение"
(втора производна на тренда, различно от linear-regression slope #46).

РЕЗУЛТАТ от 3-прозорец валидация на кръг 12 (04.11): `three_outside_up`
изглеждаше силен в прозорци 1-2 (43.7%/56.9% win rate, бие и двата
бенчмарка, положителна avg_ret и двата пъти), НО се ПРОВАЛИ напълно в
прозорец 3 (27.1% - далеч под Donchian 41.4%/random 41.7%, avg_ret
-2.44%, най-лошият резултат в целия кръг) - класически multiple-testing
шум, отхвърлен ОКОНЧАТЕЛНО въпреки силното начало. ЕДИНСТВЕНИЯТ истински
3/3 survivor: `chopbreak_n14` - бие и двата бенчмарка по win_rate, hit_
target_10pct, И avg_ret във ВСИЧКИТЕ 3 прозореца (48.7/52.9/52.9% win
rate, винаги положителна avg_ret +0.44/+0.81/+0.23%). ЧЕСТНА бележка:
тънка извадка (34-85 сигнала, 11-17 тикера на прозорец - по-малко от
ulcerlowbreak кандидатите от кръг 11). `maaccel_w10` показа 2/3 победи
но смесен резултат в прозорец 1 - недостатъчно стабилен. `camarilla_h3/
l3` произвеждат хиляди сигнали но без реален марж над baseline - просто
следват общото движение на пазара в съответния прозорец.

КРЪГ 13 (04.11, по молба "още"): 9 НОВИ механично различни семейства (18
нови варианта, 382 единични общо), проверени предварително срещу
strategies.py каталога - Pocket Pivot НАРОЧНО пропуснат (вече тестван
там, смесен резултат); RSI "failure swing" ОТХВЪРЛЕН на етап планиране
(концептуално твърде близък до вече тествания rsi_bulldiv #46 - и двата
са "RSI по-високо дъно докато цената по-ниско" формации), заменен с
Donchian канал позиция-процентил. VPCI (Volume Price Confirmation
Indicator, опростено), Chaikin Volatility разширение (темп на промяна в
размаха, различно от абсолютното ниво на ATR разширение #33), PVI
(Positive Volume Index нов връх, огледално на NVI #85), Donchian канал
позиция-процентил (непрекъсната метрика, аналог на Bollinger %B #62 но
за Donchian геометрия), "Outside day" reversal (единичен ден, ЦЯЛ
диапазон поглъща вчерашния - различно от 3-дневния three_outside_up
#102), Random Walk Index (сравнява реалното движение срещу очакваното
от ЧИСТ случаен разходка - статистически тест за неслучайност, различен
от всичко досегашно), Schaff Trend Cycle (опростено - Stochastic върху
MACD, различна цел от Stochastic RSI #67), KST/Know Sure Thing (4
претеглени ROC-а, различно от Coppock #60's 2 равнотежени), и
регресионен канал ДОЛНА лента отскок (огледално на regchannel #54, k=-2.0
вместо +2.0 в същата _regression_channel_upper функция). РЕЗУЛТАТ:
предстои 3-прозорец валидация - виж по-долу.

ЗАЩО ВЕКТОРИЗИРАНО, а не като strategy_backtest.py:
  strategy_backtest.py извиква всяка STRATEGIES[name](df.iloc[:i+1]) НА
  ВСЕКИ ден отделно - за 26 стратегии върху ~170 дни това е ~4420 извиквания
  на ден-по-ден растящ прозорец (O(дни^2) ефективно, защото rolling
  индикаторите се преизчисляват от начало всеки път). За 139 единични
  + 9591 комбинации това би било неизползваемо бавно. Тук всеки индикатор
  (rolling max/mean/std, RSI, MA) се смята ЕДИН път върху ЦЕЛАТА серия с
  pandas/numpy (истински вектор операции, O(дни) общо на тикер), а
  комбинациите от по 2 се генерират само измежду стратегиите, които РЕАЛНО
  са "гръмнали" в същия ден (itertools.combinations върху малкия списък
  "гръмнали днес", не върху всичките 9591 възможни двойки всеки ден).

ЧЕСТНИ ОГРАНИЧЕНИЯ (важат В ДОПЪЛНЕНИЕ към всичко описано в горния модул
strategy_backtest.py - дневни свещи, universe survivorship bias, без
spread/комисионни - прочети и тях):

  1. MULTIPLE-TESTING РИСК Е МНОГО ПО-ГОЛЯМ ТУК. strategy_backtest.py вече
     показа 9 поредни кръга, че "обещаващи" находки от 20-30 единични
     стратегии и 55-325 комбинации НЕ издържат извън-извадкова проверка
     (--offset-days). Тук тестваме НАД 109 000 комбинации - при толкова
     много "опити", чисто случайно ДЕСЕТИНА ще изглеждат отлични дори ако
     НИТО една няма истинско предимство. Затова:
       - МИНИМАЛЕН праг от --min-signals (по подразбиране 30) сигнала,
         разпределени на --min-symbols (по подразбиране 3) различни тикера,
         преди да се докладва каквото и да е (виж COMBO_MIN_SIGNALS=25 в
         strategy_backtest.py - тук прагът е по-строг, защото е-претърсено
         МНОГО повече пространство).
       - Класирането на топ 10 е ПО ЕДИН предварително избран хоризонт
         (--main-exit, по подразбиране close_5d), НЕ по "най-добрия от
         5 изхода за тази стратегия" - ако позволим да се избира и изходът
         след факта, добавяме ОЩЕ един слой multiple-testing (5x повече
         "опити" на стратегия).
       - ЗАДЪЛЖИТЕЛНО: топ 10 от ЕДИН прозорец (--days 250) НЕ значи нищо
         сам по себе си - виж ИЗВЪН-ИЗВАДКОВА ВАЛИДАЦИЯ по-долу, същият
         протокол като във strategy_backtest.py.
  2. "sub-никелови" (<$0.05) тикери са директно ИЗКЛЮЧЕНИ от самото начало
     (не само отбелязани като в strategy_backtest.py) - предишни кръгове
     показаха, че тези "zombie" тикери произвеждат фалшиво екстремни
     числа (reverse split артефакти, dilution спирали), а тук с хиляди
     комбинации нямаме капацитет да проверяваме всяка ръчно.
  3. "overnight" изход (next_open: купуваш на close, продаваш на
     следващия open) е ОПРОСТЕН модел на идеята "затварят в 11 вечер
     София време, скачат overnight" - НЕ симулира extended-hours търговия,
     gap risk при лоши новини, или факта, че penny stocks могат да имат
     широк spread точно на открита на сесията. Третира се РАВНОПОСТАВЕНО
     с close_1d/3d/5d/10d - по изрична молба ("няма значение дали е
     overnight при отваряне няма значение").
  4. Не се пазят ВСИЧКИ отделни сделки в CSV (за разлика от
     backtest_trades.csv в strategy_backtest.py) - с хиляди тествани
     комбинации пълният ред-по-ред CSV би бил с милиони редове. Пазят се
     само резюметата (mass_search_singles_summary.csv,
     mass_search_combos_summary.csv, mass_search_top10.csv).

ИЗВЪН-ИЗВАДКОВА ВАЛИДАЦИЯ (ЗАДЪЛЖИТЕЛНА, същият протокол като
strategy_backtest.py - виж неговите коментари за пълно обяснение):
    python mass_strategy_search.py --days 250
    python mass_strategy_search.py --days 250 --offset-days 250
    python mass_strategy_search.py --days 250 --offset-days 500
Топ 10 от ТРИТЕ прозорца се сравняват ръчно - НАИСТИНА добра стратегия
трябва да се показва стабилно (сходен win rate, положителна средна
доходност, по-добра от random_baseline) във ВСИЧКИ 3 прозорца, не само в
първия. Ако изчезва/обръща знак между прозорците - шум, не ефект (виж
ichimoku_kijun_cross в strategy_backtest.py кръг 8 за точно такъв пример).

Употреба:
    python mass_strategy_search.py --days 250 --top 10
    python mass_strategy_search.py --days 250 --no-combos   (само единичните
        варианти, много по-бързо, за бърза проверка)
    python mass_strategy_search.py --days 250 --target-pct 15 --stop-pct 20
        (друга цел/stop за take-profit симулацията, напр. "искам 15%+")
    python mass_strategy_search.py --days 250 --rank-by win_rate
        (класирай по старото win_rate класиране вместо hit_target_Xpct)
"""
import argparse
import itertools
import logging

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import BDay, CustomBusinessDay

import config
from strategy_backtest import SUBNICKEL_PRICE_FLOOR, _get_universe_symbols, load_history

# КРЪГ 8: реален US federal holiday календар (не аритметика на датата) -
# ползва се от calendar_pre_holiday/calendar_post_holiday семейството в
# build_signal_library по-долу. Конструиран ВЕДНЪЖ на module level (не на
# всяко извикване на build_signal_library/на всеки тикер) - USFederalHolidayCalendar()
# и CustomBusinessDay() не зависят от df, пресъздаването им хиляди пъти би
# било чисто прахосан разход.
_HOLIDAY_CBD = CustomBusinessDay(calendar=USFederalHolidayCalendar())

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("mass_strategy_search")

# Същата идея като RANDOM_BASELINE_EVERY_NTH_DAY в strategy_backtest.py -
# контролна група от случайни дни (без сигнал), за да има истинско
# сравнение "бие ли случаен вход".
RANDOM_BASELINE_EVERY_NTH_DAY = 10

# По-строг праг от COMBO_MIN_SIGNALS=25 в strategy_backtest.py - виж
# честната бележка #1 по-горе за защо (много по-голямо претърсено
# пространство тук).
DEFAULT_MIN_SIGNALS = 30
DEFAULT_MIN_SYMBOLS = 3

# "Изходи" (кога продаваме спрямо входната цена при close(i)):
#   next_open  = продаваме на OPEN на СЛЕДВАЩИЯ ден (overnight hold -
#                идеята "затварят в 11 вечер, скачат overnight")
#   close_Nd   = продаваме на CLOSE след N търговски дни (същото като
#                ret_{h}d_pct в strategy_backtest.py)
EXITS = ["next_open", "close_1d", "close_3d", "close_5d", "close_10d"]
# За кои изходи смятаме и "хванахме ли скока" (max high през хоризонта,
# не само затварянето - виж честната бележка в strategy_backtest.py за
# maxrunup_by_horizon). next_open няма смисъл тук (хоризонтът е 1 ден,
# без междинни дни за "връх по пътя").
RUNUP_HORIZON = {"close_1d": 1, "close_3d": 3, "close_5d": 5, "close_10d": 10}
MAX_HORIZON_DAYS = 10

# Най-дългият rolling прозорец измежду всичките параметризирани семейства
# по-долу (MA кросоувър slow=100) - плюс буфер. Дни преди този индекс
# нямат достатъчно история за ВСИЧКИ семейства да бъдат надеждно смятани.
MIN_BARS = 110

# КРЪГ 2 (03.11) - целева печалба/stop за реалистична take-profit
# симулация (виж _simulate_target_stop_return по-долу и честната бележка
# в docstring-а за точната логика - stop се проверява ПРЕДИ target на
# всеки ден, консервативно, по същата философия като STOP_LOSS_PCT в
# strategy_backtest.py). Променят се с --target-pct/--stop-pct.
DEFAULT_TARGET_PCT = 10.0
DEFAULT_STOP_PCT = 15.0


def _parabolic_sar_flip(high: np.ndarray, low: np.ndarray, af_start: float, af_step: float, af_max: float) -> np.ndarray:
    """КРЪГ 3: Wilder Parabolic SAR - ЕДИНСТВЕНОТО тук stateful/итеративно
    изчисление (SAR днес зависи от SAR вчера, не rolling прозорец върху
    фиксиран брой дни). Връща True на ДЕНЯ, в който трендът обръща от
    низходящ към възходящ (бичи flip) - сигналът, не целия SAR ред.
    Единен python loop, O(n) на тикер на вариант (не O(n^2) - виж честната
    бележка в началото на модула защо това НЕ е проблем тук)."""
    n = len(high)
    flip = np.zeros(n, dtype=bool)
    if n < 3:
        return flip
    uptrend = True
    sar = low[0]
    ep = high[0]
    af = af_start
    for i in range(1, n):
        if uptrend:
            sar_i = sar + af * (ep - sar)
            sar_i = min(sar_i, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < sar_i:
                # мечи flip (up->down) - НЕ е нашият сигнал, не маркираме flip[i].
                uptrend = False
                sar_i = ep
                ep = low[i]
                af = af_start
            elif high[i] > ep:
                ep = high[i]
                af = min(af + af_step, af_max)
        else:
            sar_i = sar + af * (ep - sar)
            sar_i = max(sar_i, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > sar_i:
                uptrend = True
                sar_i = ep
                ep = high[i]
                af = af_start
                flip[i] = True
            elif low[i] < ep:
                ep = low[i]
                af = min(af + af_step, af_max)
        sar = sar_i
    return flip


def _supertrend_flip(high: np.ndarray, low: np.ndarray, close: np.ndarray, atr: np.ndarray, multiplier: float) -> np.ndarray:
    """КРЪГ 5: Supertrend (стандартна формула) - ВТОРОТО stateful/итеративно
    изчисление тук покрай _parabolic_sar_flip (финалните upper/lower ленти
    на днешния бар зависят от вчерашните финални ленти, не само от
    rolling прозорец върху фиксиран брой дни - затова не може да се
    изчисли чисто векторизирано). `atr` се подава ОТВЪН (вече изчислен
    векторизирано с pandas ewm извън тази функция) - само state-машината
    за final upper/lower/trend е същински python loop, O(n) на тикер на
    вариант. Връща True САМО на деня, в който трендът обръща от низходящ
    към възходящ (бичи flip), по същата конвенция като PSAR по-горе."""
    n = len(close)
    flip = np.zeros(n, dtype=bool)
    if n < 2:
        return flip
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    trend_up = np.zeros(n, dtype=bool)
    final_upper[0] = basic_upper[0]
    final_lower[0] = basic_lower[0]
    trend_up[0] = True
    for i in range(1, n):
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]
        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]
        if trend_up[i - 1]:
            trend_up[i] = not (close[i] < final_lower[i])
        else:
            if close[i] > final_upper[i]:
                trend_up[i] = True
                flip[i] = True
            else:
                trend_up[i] = False
    return flip


def _anchored_vwap_flip(low: np.ndarray, typical_price: np.ndarray, vol: np.ndarray, close: np.ndarray, lookback_w: int) -> np.ndarray:
    """КРЪГ 7: "Anchored" VWAP с ДИНАМИЧЕН анкер - за всеки ден i анкерът е
    индексът на НАЙ-НИСКОТО low през последните lookback_w дни (sliding
    window argmin, вектор ризирано чрез sliding_window_view), а самият VWAP
    е КУМУЛАТИВНА сума ОТ този анкер насам (чрез prefix sums - O(1) на ден
    след предварителното изчисление) - ТРЕТОТО stateful/итеративно
    изчисление тук (покрай PSAR #25 и Supertrend #47), защото анкерът се
    мести всеки ден и не е rolling прозорец с ФИКСИРАНА дължина като
    vwap_reclaim #24. Връща True на деня, в който цената пресича нагоре
    anchored VWAP линията (изчислена със СЪЩИЯ анкер и за вчера, и за днес,
    за коректно сравнение "вчера под/днес над")."""
    n = len(close)
    flip = np.zeros(n, dtype=bool)
    if n <= lookback_w + 1:
        return flip
    tpv = typical_price * vol
    cum_tpv = np.concatenate(([0.0], np.cumsum(tpv)))
    cum_vol = np.concatenate(([0.0], np.cumsum(vol)))
    windows = sliding_window_view(low, lookback_w)
    argmins = np.argmin(windows, axis=1)
    for i in range(lookback_w, n):
        anchor_idx = (i - lookback_w + 1) + argmins[i - (lookback_w - 1)]
        seg_vol_today = cum_vol[i + 1] - cum_vol[anchor_idx]
        seg_vol_prev = cum_vol[i] - cum_vol[anchor_idx]
        if seg_vol_today <= 0 or seg_vol_prev <= 0:
            continue
        vwap_today = (cum_tpv[i + 1] - cum_tpv[anchor_idx]) / seg_vol_today
        vwap_prev = (cum_tpv[i] - cum_tpv[anchor_idx]) / seg_vol_prev
        if close[i - 1] <= vwap_prev and close[i] > vwap_today:
            flip[i] = True
    return flip


def _chandelier_exit_flip(highest_high: np.ndarray, lowest_low: np.ndarray, close: np.ndarray, atr: np.ndarray, multiplier: float) -> np.ndarray:
    """КРЪГ 8: Chandelier Exit (Chuck LeBeau) - ЧЕТВЪРТОТО stateful/итеративно
    изчисление тук (покрай PSAR #25, Supertrend #47, Anchored VWAP #55). За
    разлика от Supertrend (чиято "basic" лента е (H+L)/2 ПРЕИЗЧИСЛЕНА всеки
    ден), тук "дългата" стоп-линия е highest_high[i] - mult*atr[i], но се
    "тресчи" (ratchet) - може само да РАСТЕ, докато трендът е възходящ
    (взима max спрямо вчерашната финална линия); аналогично "късата" линия
    lowest_low[i] + mult*atr[i] може само да ПАДА при низходящ тренд.
    Връща True на деня, в който цената пресича НАГОРЕ през текущата
    (ratchet-нала) стоп-линия, обръщайки от низходящ към възходящ тренд -
    същата конвенция като _supertrend_flip по-горе. `highest_high`/
    `lowest_low`/`atr` се подават ОТВЪН (вече изчислени векторизирано с
    pandas rolling/ewm извън тази функция) - само ratchet state-машината
    е същински python loop, O(n) на тикер на вариант."""
    n = len(close)
    flip = np.zeros(n, dtype=bool)
    if n < 2:
        return flip
    in_uptrend = True
    stop_level = np.nan
    for i in range(1, n):
        if np.isnan(highest_high[i]) or np.isnan(lowest_low[i]) or np.isnan(atr[i]):
            continue
        if in_uptrend:
            candidate = highest_high[i] - multiplier * atr[i]
            stop_level = candidate if np.isnan(stop_level) else max(stop_level, candidate)
            if close[i] < stop_level:
                in_uptrend = False
                stop_level = lowest_low[i] + multiplier * atr[i]
        else:
            candidate = lowest_low[i] + multiplier * atr[i]
            stop_level = candidate if np.isnan(stop_level) else min(stop_level, candidate)
            if close[i] > stop_level:
                in_uptrend = True
                flip[i] = True
                stop_level = highest_high[i] - multiplier * atr[i]
    return flip


def _mcginley_dynamic(close: np.ndarray, n: float) -> np.ndarray:
    """КРЪГ 9: McGinley Dynamic - ПЕТОТО stateful/итеративно изчисление тук
    (покрай PSAR #25, Supertrend #47, Anchored VWAP #55, Chandelier Exit
    #59). Самоадаптираща се пълзяща средна - СКОРОСТТА, с която линията
    "гони" цената, зависи от съотношението close[i]/MD[i-1] на ЧЕТВЪРТА
    степен (различно от ВСЯКА друга средна тук - SMA/EMA/SMMA/WMA имат
    ФИКСИРАНА скорост, независима от текущата цена) - затова не може да се
    изчисли векторизирано, MD[i] зависи рекурсивно от MD[i-1] по НЕЛИНЕЕН
    начин. ЧЕСТНА защита: съотношението close[i]/MD[i-1] се ограничава до
    [0.5, 2.0] преди повдигане на 4-та степен - без това, един единствен
    rev-split/gap ден при penny stocks (цена пада 10x за една свещ) би
    докарал знаменателя до практическо 0 и MD до inf/nan за остатъка от
    серията."""
    length = len(close)
    md = np.empty(length)
    md[0] = close[0]
    for i in range(1, length):
        prev = md[i - 1]
        if prev == 0 or np.isnan(prev) or close[i] != close[i]:
            md[i] = close[i]
            continue
        ratio = close[i] / prev
        ratio = min(max(ratio, 0.5), 2.0)
        denom = n * ratio ** 4
        md[i] = close[i] if denom == 0 else prev + (close[i] - prev) / denom
    return md


def _kama(close: np.ndarray, er_period: int, fast_period: int = 2, slow_period: int = 30) -> np.ndarray:
    """КРЪГ 12: Kaufman Adaptive Moving Average - ШЕСТОТО stateful/
    итеративно изчисление тук (покрай PSAR #25, Supertrend #47, Anchored
    VWAP #55, Chandelier Exit #59, McGinley Dynamic #74). За разлика от
    McGinley (скоростта зависи от СЪОТНОШЕНИЕТО цена/предишна-стойност),
    тук скоростта зависи от Efficiency Ratio - колко "ефективно" (право,
    без шум) се е движила цената през последните er_period дни
    (|нетна промяна| / сума от |дневни промени|, 0=чист шум, 1=права
    линия) - затова е stateful: smoothing constant SC[i] се сменя всеки
    ден спрямо ER[i], и KAMA[i] = KAMA[i-1] + SC[i]*(close[i]-KAMA[i-1])
    рекурсивно зависи от KAMA[i-1]."""
    length = len(close)
    kama = np.empty(length)
    if length == 0:
        return kama
    kama[0] = close[0]
    fast_sc = 2.0 / (fast_period + 1)
    slow_sc = 2.0 / (slow_period + 1)
    abs_diff = np.abs(np.diff(close, prepend=close[0]))
    for i in range(1, length):
        if i < er_period:
            kama[i] = close[i] if np.isnan(kama[i - 1]) else kama[i - 1] + (close[i] - kama[i - 1]) * fast_sc
            continue
        if close[i] != close[i]:
            kama[i] = kama[i - 1]
            continue
        change = abs(close[i] - close[i - er_period])
        volatility = abs_diff[i - er_period + 1: i + 1].sum()
        er = 0.0 if volatility == 0 else change / volatility
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        prev = kama[i - 1]
        kama[i] = close[i] if np.isnan(prev) else prev + sc * (close[i] - prev)
    return kama


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def build_signal_library(df: pd.DataFrame, benchmark_close: pd.Series = None) -> dict:
    """Връща {име_на_вариант: numpy bool масив, дължина = len(df)}.
    Всичко смятано ВЕКТОРИЗИРАНО (pandas rolling/shift/ewm) върху ЦЕЛАТА
    серия наведнъж - виж обяснението в началото на модула защо това е
    задължително при хиляди варианти. `benchmark_close` (кръг 3,
    незадължителен) - пазарен бенчмарк (напр. SPY), ВЕЧЕ reindex-нат към
    df.index от извикващия (виж process_symbol) - ползва се само от
    relative-strength семейството #26; ако е None, семейството просто не
    генерира сигнали (не греши)."""
    close, high, low, open_, vol = df["close"], df["high"], df["low"], df["open"], df["volume"]
    sig = {}

    # 1) Donchian breakout по HIGH (price-channel пробив + обемно
    #    потвърждение) - 6 прозореца x 4 обемни множителя = 24 варианта.
    for w in (10, 15, 20, 30, 40, 55):
        prior_high_max = high.rolling(w).max().shift(1)
        prior_vol_mean = vol.rolling(w).mean().shift(1)
        base = close > prior_high_max
        for vm in (1.0, 1.5, 2.0, 3.0):
            sig[f"donch_h_w{w}_v{vm}"] = (base & (vol >= vm * prior_vol_mean)).fillna(False).to_numpy()

    # 2) Donchian breakout по CLOSE (по-мек от #1, не изисква пробив над
    #    HIGH, само над предишни затваряния) - "чист" вариант (6) + с
    #    обемен филтър (6x3=18) = 24 варианта.
    for w in (10, 15, 20, 30, 40, 55):
        prior_close_max = close.rolling(w).max().shift(1)
        prior_vol_mean = vol.rolling(w).mean().shift(1)
        base = close > prior_close_max
        sig[f"donch_c_w{w}"] = base.fillna(False).to_numpy()
        for vm in (1.5, 2.0, 3.0):
            sig[f"donch_c_w{w}_v{vm}"] = (base & (vol >= vm * prior_vol_mean)).fillna(False).to_numpy()

    # 3) Чист обемен скок (без изискване за пробив на нова цена, само
    #    "днес не е надолу ден") - 3 прозореца x 4 множителя = 12.
    for w in (10, 20, 30):
        prior_vol_mean = vol.rolling(w).mean().shift(1)
        for vm in (2.0, 3.0, 5.0, 8.0):
            s = (vol >= vm * prior_vol_mean) & (close > close.shift(1))
            sig[f"volspike_w{w}_v{vm}"] = s.fillna(False).to_numpy()

    # 4) Моментум / Rate-of-Change - 4 периода x 5 прага = 20.
    for n in (3, 5, 10, 20):
        roc = close / close.shift(n) - 1
        for t in (0.05, 0.10, 0.15, 0.20, 0.30):
            sig[f"roc_n{n}_t{t}"] = (roc >= t).fillna(False).to_numpy()

    # 5) RSI превишаване нагоре на ниво (bounce от oversold) - 3 периода
    #    x 4 нива = 12.
    for p in (7, 14, 21):
        rsi_series = _rsi(close, p)
        rsi_prev = rsi_series.shift(1)
        for lvl in (20, 25, 30, 35):
            s = (rsi_prev < lvl) & (rsi_series >= lvl)
            sig[f"rsi_p{p}_l{lvl}"] = s.fillna(False).to_numpy()

    # 6) Gap-up и задържане над отварянето (OPEN спрямо предишен CLOSE,
    #    различно измерение от всичко останало тук) - 4 gap прага x 3
    #    "задържане" прага = 12.
    gap = open_ / close.shift(1) - 1
    for gt in (0.05, 0.10, 0.15, 0.20):
        for hf in (0.90, 0.95, 1.00):
            s = (gap >= gt) & (close >= open_ * hf)
            sig[f"gap_g{gt}_h{hf}"] = s.fillna(False).to_numpy()

    # 7) Pullback-to-high mean reversion завой (дръпване X-Y% от скорошен
    #    връх, ПЪРВИЯТ зелен ден) - 3 прозореца x 3 диапазона = 9.
    for w in (10, 20, 40):
        roll_max = close.rolling(w).max().shift(1)
        pullback_pct = (roll_max - close) / roll_max
        for lo, hi in ((0.10, 0.30), (0.20, 0.40), (0.30, 0.50)):
            s = (close > close.shift(1)) & (pullback_pct >= lo) & (pullback_pct <= hi)
            sig[f"pullback_w{w}_{lo}_{hi}"] = s.fillna(False).to_numpy()

    # 8) Moving-average кросоувър (fast пресича slow нагоре) - 8 валидни
    #    (fast<slow) комбинации.
    ma_cache = {p: close.rolling(p).mean() for p in (5, 10, 20, 50, 100)}
    for f, s in ((5, 20), (5, 50), (5, 100), (10, 20), (10, 50), (10, 100), (20, 50), (20, 100)):
        fast_ma, slow_ma = ma_cache[f], ma_cache[s]
        sig_s = (fast_ma.shift(1) <= slow_ma.shift(1)) & (fast_ma > slow_ma)
        sig[f"macross_f{f}_s{s}"] = sig_s.fillna(False).to_numpy()

    # 9) Bollinger "squeeze" (ниска волатилност) последвано от пробив над
    #    горната лента - 3 периода x 3 k-множителя = 9.
    for p in (10, 20, 30):
        ma = close.rolling(p).mean()
        std = close.rolling(p).std()
        for k in (1.5, 2.0, 2.5):
            upper = ma + k * std
            lower = ma - k * std
            bandwidth = (upper - lower) / ma
            squeeze = bandwidth <= bandwidth.rolling(50).quantile(0.20)
            s = squeeze.shift(1) & (close > upper)
            sig[f"bbsqueeze_p{p}_k{k}"] = s.fillna(False).to_numpy()

    # 10) "Near-high" с растящ обем (цена близо до N-дневен връх + обемът
    #     расте 2 последователни дни) - 3 прозореца x 3 "колко близо" = 9.
    for w in (10, 20, 40):
        roll_max_incl = close.rolling(w).max()
        vol_rising = (vol > vol.shift(1)) & (vol.shift(1) > vol.shift(2))
        for np_ in (0.95, 0.98, 1.00):
            s = (close >= roll_max_incl * np_) & vol_rising
            sig[f"nearhigh_w{w}_n{np_}"] = s.fillna(False).to_numpy()

    # === КРЪГ 2 (03.11, по молба "давай нови други стратегии") - 9 НОВИ
    # механично различни семейства, 27 нови варианта. Нарочно от различни
    # "училища" на техническия анализ - виж горния docstring КРЪГ 2(а).

    # 11) OBV (On-Balance-Volume) пробив - обемът "лидира" цената: OBV прави
    #     нов N-дневен връх ПРЕДИ цената да го направи - различно измерение
    #     от чист volspike (там гледаме САМО днешния обем, тук кумулативна
    #     посока на обема през времето). 3 прозореца x (чист пробив на OBV +
    #     "лидер" вариант, където цената ОЩЕ не е пробила) = 6.
    obv = (np.sign(close.diff()).fillna(0) * vol).cumsum()
    for w in (10, 20, 30):
        obv_roll_max = obv.rolling(w).max().shift(1)
        close_roll_max = close.rolling(w).max().shift(1)
        base = obv > obv_roll_max
        sig[f"obv_breakout_w{w}"] = base.fillna(False).to_numpy()
        sig[f"obv_lead_w{w}"] = (base & (close < close_roll_max)).fillna(False).to_numpy()

    # 12) MACD бичи кросоувър (EMA12/26 - signal линия, различно от
    #     простия MA кросоувър в #8, защото използва EMA на РАЗЛИКАТА, не
    #     директно цените) - 2 комплекта периоди x (свободен/"близо до
    #     нулата" филтър) = 4.
    for fast, slow, sigp in ((12, 26, 9), (8, 17, 9)):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=sigp, adjust=False).mean()
        cross = (macd.shift(1) <= macd_signal.shift(1)) & (macd > macd_signal)
        sig[f"macd_f{fast}_s{slow}_sig{sigp}_any"] = cross.fillna(False).to_numpy()
        sig[f"macd_f{fast}_s{slow}_sig{sigp}_nearzero"] = (cross & (macd < 0)).fillna(False).to_numpy()

    # 13) Stochastic oversold завой (%K пресича %D нагоре, идвайки от
    #     overbought/oversold ЗОНА в диапазона high/low - различно от RSI,
    #     който гледа само затварянията) - 2 периода x 2 нива = 4.
    for p in (9, 14):
        low_min = low.rolling(p).min()
        high_max = high.rolling(p).max()
        pct_k = (close - low_min) / (high_max - low_min) * 100
        pct_d = pct_k.rolling(3).mean()
        for lvl in (20, 30):
            s = (pct_k.shift(1) <= pct_d.shift(1)) & (pct_k > pct_d) & (pct_d.shift(1) < lvl)
            sig[f"stoch_p{p}_l{lvl}"] = s.fillna(False).to_numpy()

    # 14) ADX/DMI сила на тренда (Wilder) - ЧЕСТНА бележка от кръг 6 на
    #     strategy_backtest.py: прекосяване на фиксиран праг почти никога
    #     не се хваща навреме при penny stocks, затова питаме "расте ли
    #     ADX СЕГА и не е презрял" - 2 периода = 2.
    for p in (14, 20):
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        tr = pd.concat([
            high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / p, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / p, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=1 / p, adjust=False).mean() / atr
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100
        adx = dx.ewm(alpha=1 / p, adjust=False).mean()
        s = (plus_di > minus_di) & (adx > adx.shift(2)) & (adx < 40)
        sig[f"adx_p{p}"] = s.fillna(False).to_numpy()

    # 15) Bullish engulfing свещна формация - ПЪРВОТО тук чисто ценово-
    #     ФОРМЕНО семейство (не rolling индикатор от никакъв вид), японска
    #     candlestick класика - 2 "колко по-голямо тяло" прага = 2.
    body_today = close - open_
    body_prev = (close - open_).shift(1)
    for mult in (1.0, 1.5):
        s = (
            (body_prev < 0) & (body_today > 0)
            & (close > open_.shift(1)) & (open_ < close.shift(1))
            & (body_today.abs() > body_prev.abs() * mult)
        )
        sig[f"engulfing_m{mult}"] = s.fillna(False).to_numpy()

    # 16) "Three-bar tight" волатилна контракция (3 дни с намаляващ дневен
    #     диапазон - свиване ПРЕДИ движение, не пробив сам по себе си) -
    #     чист вариант + 2 по-стегнати (спрямо 20-дневния среден диапазон) = 3.
    day_range = high - low
    contraction = (day_range < day_range.shift(1)) & (day_range.shift(1) < day_range.shift(2))
    sig["threebar_tight_plain"] = contraction.fillna(False).to_numpy()
    avg_range20 = day_range.rolling(20).mean()
    for factor in (0.5, 0.7):
        s = contraction & (day_range < avg_range20 * factor)
        sig[f"threebar_tight_f{factor}"] = s.fillna(False).to_numpy()

    # 17) "Higher-low" база (серия от РАСТЯЩИ дъна на нови 5/10-дневни
    #     стъпки - форма на основата, не волатилност/обем) - 2 размера
    #     стъпка = 2.
    for step in (5, 10):
        ll = low.rolling(step).min()
        s = (ll > ll.shift(step)) & (ll.shift(step) > ll.shift(2 * step)) & (close > close.shift(1))
        sig[f"higherlow_s{step}"] = s.fillna(False).to_numpy()

    # 18) Фибоначи ретрейсмънт отскок - ГЕОМЕТРИЧНО измерване на swing
    #     колебание (целим изрично 50%/61.8% зоните, не произволен % off
    #     high като pullback семейството в #7) - 2 прозореца = 2.
    for w in (20, 40):
        swing_high = high.rolling(w).max()
        swing_low = low.rolling(w).min()
        retrace = (swing_high - close) / (swing_high - swing_low)
        in_fib_zone = retrace.between(0.45, 0.55) | retrace.between(0.58, 0.68)
        s = (close > close.shift(1)) & in_fib_zone
        sig[f"fib_bounce_w{w}"] = s.fillna(False).to_numpy()

    # 19) Elder's Force Index reclaim - тежи ПРОМЯНАТА в цената (не
    #     нивото), умножена по обема, различно от OBV (#11, кумулативно
    #     ПОСОКА) и volspike (#3, само обем) - 2 EMA периода = 2.
    force = (close - close.shift(1)) * vol
    for p in (2, 13):
        force_ema = force.ewm(span=p, adjust=False).mean()
        s = (force_ema.shift(1) <= 0) & (force_ema > 0)
        sig[f"force_p{p}"] = s.fillna(False).to_numpy()

    # === КРЪГ 3 (03.11, по молба "дай още стратегии") - 9 ОЩЕ нови
    # механично различни семейства, до 23 нови варианта.

    # 20) Keltner Channel пробив (ATR-базиран канал - различно от
    #     Bollinger #9, който е std-базиран) - 2 периода x 2 k = 4.
    tr_kc = pd.concat([
        high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    for p in (14, 20):
        ema_center = close.ewm(span=p, adjust=False).mean()
        atr_kc = tr_kc.ewm(alpha=1 / p, adjust=False).mean()
        for k in (1.5, 2.0):
            upper_kc = ema_center + k * atr_kc
            s = (close.shift(1) <= upper_kc.shift(1)) & (close > upper_kc)
            sig[f"keltner_p{p}_k{k}"] = s.fillna(False).to_numpy()

    # 21) CCI (Commodity Channel Index) oversold завой - различна формула
    #     от RSI/Stochastic (отстояние от типичната цена спрямо средното
    #     абсолютно отклонение) - 2 периода = 2.
    typical_price = (high + low + close) / 3
    for p in (14, 20):
        sma_tp = typical_price.rolling(p).mean()
        mad = typical_price.rolling(p).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        cci = (typical_price - sma_tp) / (0.015 * mad)
        s = (cci.shift(1) <= -100) & (cci > -100)
        sig[f"cci_p{p}"] = s.fillna(False).to_numpy()

    # 22) Williams %R oversold завой - позиция в high/low диапазона
    #     (огледално на Stochastic #13, но БЕЗ %D усредняване) - 2 периода = 2.
    for p in (14, 20):
        hh = high.rolling(p).max()
        ll = low.rolling(p).min()
        wr = -100 * (hh - close) / (hh - ll)
        s = (wr.shift(1) <= -80) & (wr > -80)
        sig[f"williamsr_p{p}"] = s.fillna(False).to_numpy()

    # 23) Chaikin Money Flow преминаване над 0 - обемно-претеглена
    #     accumulation/distribution (различна формула от OBV #11 и
    #     A/D line) - 2 периода = 2.
    mfm = ((close - low) - (high - close)) / (high - low)
    mfm = mfm.replace([np.inf, -np.inf], 0).fillna(0)
    mfv = mfm * vol
    for p in (14, 20):
        cmf = mfv.rolling(p).sum() / vol.rolling(p).sum()
        s = (cmf.shift(1) <= 0) & (cmf > 0)
        sig[f"cmf_p{p}"] = s.fillna(False).to_numpy()

    # 24) VWAP reclaim - цена пресича кумулативната обемно-претеглена
    #     средна цена за последните w дни (различно измерение от всичко
    #     досегашно - истинска VWAP, не просто close rolling average) -
    #     3 прозореца = 3.
    for w in (10, 20, 30):
        vwap = (typical_price * vol).rolling(w).sum() / vol.rolling(w).sum()
        s = (close.shift(1) <= vwap.shift(1)) & (close > vwap)
        sig[f"vwap_reclaim_w{w}"] = s.fillna(False).to_numpy()

    # 25) Parabolic SAR бичи flip (виж _parabolic_sar_flip по-горе) -
    #     подразбиращ се Wilder комплект + по-чувствителен = 2.
    for label, (af_start, af_step, af_max) in (
        ("default", (0.02, 0.02, 0.2)), ("sensitive", (0.03, 0.03, 0.3)),
    ):
        sig[f"psar_flip_{label}"] = _parabolic_sar_flip(high.to_numpy(), low.to_numpy(), af_start, af_step, af_max)

    # 26) Relative strength vs бенчмарк (SPY) - ЕДИНСТВЕНОТО тук
    #     ОТНОСИТЕЛНО измерение (бие ли ПАЗАРА, не просто расте ли absolute
    #     като ROC #4) - 2 периода x 2 прага = 4, САМО ако е подаден
    #     бенчмарк (иначе семейството просто не генерира нищо).
    if benchmark_close is not None and not benchmark_close.isna().all():
        bench = benchmark_close.reindex(df.index).ffill()
        for n in (10, 20):
            stock_roc = close / close.shift(n) - 1
            bench_roc = bench / bench.shift(n) - 1
            rel = stock_roc - bench_roc
            for t in (0.05, 0.10):
                sig[f"relstrength_n{n}_t{t}"] = (rel >= t).fillna(False).to_numpy()

    # 27) Volume climax reversal (капитулационно дъно) - голям обемен скок
    #     на ЧЕРВЕН ден, после ЗЕЛЕНО затваряне - различно от volspike #3
    #     (там обемният скок е на ЗЕЛЕН ден, continuation, не reversal) -
    #     2 обемни множителя = 2.
    prior_vol_mean_20 = vol.rolling(20).mean().shift(2)
    for vm in (3.0, 5.0):
        climax = (vol.shift(1) >= vm * prior_vol_mean_20) & (close.shift(1) < close.shift(2))
        s = climax & (close > close.shift(1)) & (close > open_)
        sig[f"climax_reversal_v{vm}"] = s.fillna(False).to_numpy()

    # 28) Doji (нерешителност) последван от пробив - свещна ФОРМА (като
    #     engulfing #15), комбинирана с посока - 2 толеранса за "колко малко
    #     тяло се брои за doji" = 2.
    body_sz = (close - open_).abs()
    range_sz = high - low
    for tol in (0.08, 0.15):
        doji_prev = (body_sz.shift(1) <= tol * range_sz.shift(1))
        s = doji_prev & (close > high.shift(1))
        sig[f"doji_breakout_t{tol}"] = s.fillna(False).to_numpy()

    # === КРЪГ 4 (03.11, по молба "дай още ама повече стратегии всякакви
    # давай") - 10 ОЩЕ нови механично различни семейства, 20 нови варианта.

    # 29) Aroon нагоре/надолу кросоувър - МЕРИ ВРЕМЕ (колко дни от
    #     последния връх/дъно), не ниво на цена/индикатор като всичко
    #     досегашно - 2 периода = 2.
    for p in (14, 25):
        aroon_up = high.rolling(p + 1).apply(lambda w: np.argmax(w) / p * 100, raw=True)
        aroon_down = low.rolling(p + 1).apply(lambda w: np.argmin(w) / p * 100, raw=True)
        s = (aroon_up.shift(1) <= aroon_down.shift(1)) & (aroon_up > aroon_down)
        sig[f"aroon_p{p}"] = s.fillna(False).to_numpy()

    # 30) TRIX преминаване над 0 - троен EMA-изгладен rate-of-change
    #     (различно изглаждане от MACD #12, което е ЕДИНИЧНА EMA разлика) -
    #     2 периода = 2.
    for p in (9, 15):
        ema1 = close.ewm(span=p, adjust=False).mean()
        ema2 = ema1.ewm(span=p, adjust=False).mean()
        ema3 = ema2.ewm(span=p, adjust=False).mean()
        trix = ema3.pct_change() * 100
        s = (trix.shift(1) <= 0) & (trix > 0)
        sig[f"trix_p{p}"] = s.fillna(False).to_numpy()

    # 31) MFI (Money Flow Index) oversold завой - обемно-претеглен RSI
    #     (различна формула от CMF #23, който е проста сума-съотношение,
    #     и от RSI #5, който не ползва обем изобщо) - 2 периода = 2.
    raw_money_flow = typical_price * vol
    mf_direction = np.sign(typical_price.diff())
    positive_flow = raw_money_flow.where(mf_direction > 0, 0.0)
    negative_flow = raw_money_flow.where(mf_direction < 0, 0.0)
    for p in (14, 20):
        money_ratio = positive_flow.rolling(p).sum() / negative_flow.rolling(p).sum()
        mfi = 100 - 100 / (1 + money_ratio)
        s = (mfi.shift(1) <= 20) & (mfi > 20)
        sig[f"mfi_p{p}"] = s.fillna(False).to_numpy()

    # 32) PVT (Price-Volume Trend) пробив - кумулативен обем, претеглен с
    #     ПРОЦЕНТНАТА промяна на цената (различно от OBV #11, което тегли
    #     само ЗНАКА +1/-1, не величината на промяната) - 2 прозореца = 2.
    pvt = (close.pct_change() * vol).cumsum()
    for w in (10, 20):
        pvt_roll_max = pvt.rolling(w).max().shift(1)
        s = pvt > pvt_roll_max
        sig[f"pvt_breakout_w{w}"] = s.fillna(False).to_numpy()

    # 33) ATR РАЗШИРЕНИЕ пробив - волатилността РАСТЕ бързо (обратното
    #     направление на Bollinger squeeze #9, който гледа СВИВАНЕ) - 2
    #     прага за "колко бързо расте" = 2.
    atr14 = tr_kc.ewm(alpha=1 / 14, adjust=False).mean()
    atr_ratio = atr14 / atr14.shift(5)
    for ratio_thresh in (1.5, 2.0):
        s = (atr_ratio >= ratio_thresh) & (close > close.shift(1))
        sig[f"atrexpand_r{ratio_thresh}"] = s.fillna(False).to_numpy()

    # 34) "Hammer" свещна формация (дълга долна опашка, малко тяло близо
    #     до върха на диапазона - различна ФОРМА от engulfing #15/doji #28) -
    #     2 толеранса = 2.
    lower_wick = np.minimum(open_, close) - low
    upper_wick = high - np.maximum(open_, close)
    for tol in (0.5, 0.6):
        is_hammer = (lower_wick >= tol * range_sz) & (body_sz <= 0.3 * range_sz) & (upper_wick <= 0.15 * range_sz)
        sig[f"hammer_t{tol}"] = is_hammer.fillna(False).to_numpy()

    # 35) "Three white soldiers" - 3 последователни зелени дни с растящи
    #     затваряния и малки горни опашки (МНОЖЕСТВЕНА свещна формация,
    #     различна от единичните hammer/engulfing/doji) - 2 толеранса за
    #     "колко близо до върха трябва да затвори" = 2.
    green_day = close > open_
    rising_closes = (close > close.shift(1)) & (close.shift(1) > close.shift(2))
    for tol in (0.3, 0.4):
        strong_close = (high - close) <= tol * range_sz
        s = (
            green_day & green_day.shift(1) & green_day.shift(2)
            & rising_closes & strong_close & strong_close.shift(1) & strong_close.shift(2)
        )
        sig[f"threewhitesoldiers_t{tol}"] = s.fillna(False).to_numpy()

    # 36) N-дневно дъно отскок - КОНТРАРИАН вход БЕЗ изискване за обем
    #     (огледално на Donchian пробив #1/#2, и различно от climax
    #     reversal #27, който ИЗИСКВА обемен скок) - 2 прозореца = 2.
    for w in (10, 20):
        rolled_low = low.rolling(w).min().shift(2)
        made_new_low_yesterday = close.shift(1) <= rolled_low * 1.01
        s = made_new_low_yesterday & (close > close.shift(1))
        sig[f"lowbounce_w{w}"] = s.fillna(False).to_numpy()

    # 37) Gap-down възстановяване - отваря с ГОЛЯМ gap НАДОЛУ, но
    #     затваря близо до/над предишното затваряне (REVERSAL формация,
    #     огледална на gap_up_hold #6, който е continuation) - 2 gap
    #     прага = 2.
    gap_down = open_ / close.shift(1) - 1
    for gt in (0.05, 0.10):
        s = (gap_down <= -gt) & (close >= close.shift(1) * 0.97)
        sig[f"gapdown_recovery_g{gt}"] = s.fillna(False).to_numpy()

    # 38) Elder Ray Bull Power преминаване над 0 (high спрямо EMA -
    #     различно измерение от Force Index #19, който тегли ПРОМЯНАТА
    #     в close, не разстоянието на high от средната) - 2 периода = 2.
    for p in (13, 21):
        ema_bp = close.ewm(span=p, adjust=False).mean()
        bull_power = high - ema_bp
        s = (bull_power.shift(1) <= 0) & (bull_power > 0)
        sig[f"bullpower_p{p}"] = s.fillna(False).to_numpy()

    # === КРЪГ 5 (03.11, по молба "ОЩЕ") - 10 ОЩЕ нови механично различни
    # семейства, 20 нови варианта.

    # 39) Chande Momentum Oscillator (CMO) преминаване над 0 - подобен дух
    #     на RSI #5, но СУРОВА rolling СУМА на gain/loss (не Wilder EMA
    #     изглаждане като RSI) - различна формула, различен trigger (0,
    #     не oversold ниво) - 2 периода = 2.
    gain_cmo = close.diff().clip(lower=0)
    loss_cmo = (-close.diff()).clip(lower=0)
    for p in (9, 14):
        sum_gain = gain_cmo.rolling(p).sum()
        sum_loss = loss_cmo.rolling(p).sum()
        cmo = 100 * (sum_gain - sum_loss) / (sum_gain + sum_loss)
        s = (cmo.shift(1) <= 0) & (cmo > 0)
        sig[f"cmo_p{p}"] = s.fillna(False).to_numpy()

    # 40) Ultimate Oscillator преминаване над ниво - ЕДИНСТВЕНОТО тук
    #     семейство, което смесва 3 РАЗЛИЧНИ хоризонта (7/14/28 дни) в
    #     ЕДНА метрика наведнъж (buying pressure / true range) - 2 нива
    #     прага = 2.
    prior_close_uo = close.shift(1)
    bp_uo = close - np.minimum(low, prior_close_uo)
    tr_uo = np.maximum(high, prior_close_uo) - np.minimum(low, prior_close_uo)
    avg7 = bp_uo.rolling(7).sum() / tr_uo.rolling(7).sum()
    avg14 = bp_uo.rolling(14).sum() / tr_uo.rolling(14).sum()
    avg28 = bp_uo.rolling(28).sum() / tr_uo.rolling(28).sum()
    uo = 100 * (4 * avg7 + 2 * avg14 + avg28) / 7
    for lvl in (30, 50):
        s = (uo.shift(1) <= lvl) & (uo > lvl)
        sig[f"ultosc_l{lvl}"] = s.fillna(False).to_numpy()

    # 41) Chaikin Oscillator преминаване над 0 - EMA(fast)-EMA(slow)
    #     РАЗЛИКА ВЪРХУ кумулативната Accumulation/Distribution линия
    #     (различно от CMF #23, което е проста сума-съотношение БЕЗ EMA
    #     изглаждане) - 2 комплекта периоди = 2.
    ad_line = mfv.cumsum()
    for fast, slow in ((3, 10), (5, 15)):
        ema_f = ad_line.ewm(span=fast, adjust=False).mean()
        ema_s = ad_line.ewm(span=slow, adjust=False).mean()
        chosc = ema_f - ema_s
        s = (chosc.shift(1) <= 0) & (chosc > 0)
        sig[f"chaikinosc_f{fast}_s{slow}"] = s.fillna(False).to_numpy()

    # 42) Класически floor-trader Pivot Point пробив над R1/R2 - ФИКСИРАНА
    #     геометрична формула от ВЧЕРАШНИЯ бар (pivot=(H+L+C)/3), не
    #     rolling прозорец върху много дни като всичко останало тук - 2
    #     нива съпротива = 2.
    prior_high_pp, prior_low_pp, prior_close_pp = high.shift(1), low.shift(1), close.shift(1)
    pivot_pp = (prior_high_pp + prior_low_pp + prior_close_pp) / 3
    r1_pp = 2 * pivot_pp - prior_low_pp
    r2_pp = pivot_pp + (prior_high_pp - prior_low_pp)
    sig["pivot_r1"] = ((prior_close_pp <= r1_pp) & (close > r1_pp)).fillna(False).to_numpy()
    sig["pivot_r2"] = ((prior_close_pp <= r2_pp) & (close > r2_pp)).fillna(False).to_numpy()

    # 43) NR7/NR4 ("narrowest range") пробив - КОНКРЕТЕН ден с НАЙ-тесен
    #     дневен диапазон измежду последните N дни, после пробив над
    #     неговия връх (различно от three-bar-tight #16, което гледа само
    #     3 последователни СВИВАЩИ СЕ дни, не "най-тесния измежду N") - 2
    #     варианта = 2.
    for nr_n in (7, 4):
        is_nr = day_range <= day_range.rolling(nr_n).min()
        s = is_nr.shift(1) & (close > high.shift(1))
        sig[f"nr{nr_n}_breakout"] = s.fillna(False).to_numpy()

    # 44) Inside-bar пробив - класическа ЦЕНОВА ФОРМА: вчерашният бар
    #     ИЗЦЯЛО в диапазона на деня преди него, после днешно затваряне над
    #     вчерашния връх (различна форма от engulfing/hammer/doji/
    #     threewhitesoldiers) - чист + "стегнат" (вчерашният диапазон под
    #     60% от предишния) = 2.
    is_inside = (high.shift(1) <= high.shift(2)) & (low.shift(1) >= low.shift(2))
    inside_range = high.shift(1) - low.shift(1)
    prior_range_ib = high.shift(2) - low.shift(2)
    sig["insidebar_plain"] = (is_inside & (close > high.shift(1))).fillna(False).to_numpy()
    tight_ib = is_inside & (inside_range <= 0.6 * prior_range_ib) & (close > high.shift(1))
    sig["insidebar_tight"] = tight_ib.fillna(False).to_numpy()

    # 45) Linear-regression slope обрат - НАКЛОН на най-малки квадрати
    #     (OLS) на затварянията през rolling прозорец обръща от <=0 към >0
    #     (различна математика от MA кросоувър #8, което сравнява ДВЕ
    #     нива на цената, не наклон на права през всичките точки) - 2
    #     прозореца = 2.
    def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
        x = np.arange(window, dtype=float)
        x_mean = x.mean()
        x_var = ((x - x_mean) ** 2).sum()

        def _slope(y):
            return float(((x - x_mean) * (y - y.mean())).sum() / x_var)

        return series.rolling(window).apply(_slope, raw=True)

    for w in (10, 20):
        slope = _rolling_slope(close, w)
        s = (slope.shift(1) <= 0) & (slope > 0)
        sig[f"linreg_slope_w{w}"] = s.fillna(False).to_numpy()

    # 46) RSI "бичи дивергенция" - цената е близо до своето N-дневно дъно,
    #     НО RSI е ясно НАД своето СОБСТВЕНО N-дневно дъно (моментумът не
    #     потвърждава новата слабост в цената) - ПЪРВОТО тук семейство,
    #     което сравнява относителен екстремум на ИНДИКАТОР към СЕБЕ СИ
    #     през времето, различно от relstrength #26 (там сравняваме
    #     АКЦИЯТА към БЕНЧМАРК, не индикатор към себе си) - 2 прозореца = 2.
    rsi14_div = _rsi(close, 14)
    for w in (10, 20):
        roll_low_price = close.rolling(w).min()
        roll_low_rsi = rsi14_div.rolling(w).min()
        near_price_low = close <= roll_low_price * 1.01
        rsi_elevated = rsi14_div >= roll_low_rsi + 10
        s = near_price_low & rsi_elevated & (close > close.shift(1))
        sig[f"rsi_bulldiv_w{w}"] = s.fillna(False).to_numpy()

    # 47) Supertrend бичи flip (виж _supertrend_flip по-горе) - ВТОРОТО
    #     stateful/итеративно изчисление тук покрай Parabolic SAR #25,
    #     различна ATR-базирана state-машина от статичния Keltner #20
    #     канал - период 10, 2 множителя = 2.
    atr_st = tr_kc.ewm(alpha=1 / 10, adjust=False).mean().to_numpy()
    for mult in (2.0, 3.0):
        sig[f"supertrend_m{mult}"] = _supertrend_flip(high.to_numpy(), low.to_numpy(), close.to_numpy(), atr_st, mult)

    # 48) Awesome Oscillator (Bill Williams) - SMA5 МИНУС SMA34 на
    #     (high+low)/2 - различно изглаждане/период от всичко досегашно
    #     (две ПРОСТИ, не EMA, пълзящи средни на средната точка high/low,
    #     не на close) - нулева линия пресичане + "ускорение" (АО расте 2
    #     дни подред, докато е още отрицателен - по-рано предупреждение) = 2.
    midpoint_ao = (high + low) / 2
    ao = midpoint_ao.rolling(5).mean() - midpoint_ao.rolling(34).mean()
    sig["awesome_cross"] = ((ao.shift(1) <= 0) & (ao > 0)).fillna(False).to_numpy()
    accel = (ao < 0) & (ao > ao.shift(1)) & (ao.shift(1) > ao.shift(2))
    sig["awesome_accel"] = accel.fillna(False).to_numpy()

    # === КРЪГ 6 (03.11, по молба "дай други" след кръг 5) - 10 ОЩЕ нови
    # механично различни семейства, 20 нови варианта.

    # 49) Donchian MIDLINE пробив - цена пресича СРЕДАТА на N-дневния
    #     high/low канал (различна точка на пробив от donch_h #1, който
    #     изисква пробив над САМИЯ връх, и donch_c #2, който гледа
    #     затварянето) - 2 прозореца = 2.
    for w in (20, 40):
        prior_high_max_dm = high.rolling(w).max().shift(1)
        prior_low_min_dm = low.rolling(w).min().shift(1)
        midline = (prior_high_max_dm + prior_low_min_dm) / 2
        s = (close.shift(1) <= midline) & (close > midline)
        sig[f"donch_mid_w{w}"] = s.fillna(False).to_numpy()

    # 50) VWMA (Volume-Weighted MA) кросоувър - fast/slow ОБЕМНО-претеглени
    #     средни (различна формула от macross #8, който е ПРОСТА SMA, и от
    #     VWAP reclaim #24, което е ЕДНА кумулативна линия, не кросоувър
    #     на две) - 2 комплекта периоди = 2.
    def _vwma(c, v, w):
        return (c * v).rolling(w).sum() / v.rolling(w).sum()

    for f, s_ in ((10, 30), (10, 50)):
        vwma_f = _vwma(close, vol, f)
        vwma_s = _vwma(close, vol, s_)
        sgnl = (vwma_f.shift(1) <= vwma_s.shift(1)) & (vwma_f > vwma_s)
        sig[f"vwma_cross_f{f}_s{s_}"] = sgnl.fillna(False).to_numpy()

    # 51) ROC "ускорение" (втора производна на моментума - разликата на
    #     ROC от ден на ден обръща от <=0 към >0, ПРИ положителен ROC) -
    #     различна математика от roc #4 (само първата разлика) и linreg
    #     slope #45 (наклон на права през прозорец, не ден-по-ден разлика
    #     на вече изчислен индикатор) - 2 периода = 2.
    for n in (5, 10):
        roc_ra = close / close.shift(n) - 1
        roc_accel = roc_ra.diff()
        s = (roc_accel.shift(1) <= 0) & (roc_accel > 0) & (roc_ra > 0)
        sig[f"rocaccel_n{n}"] = s.fillna(False).to_numpy()

    # 52) Обемен осцилатор (fast/slow SMA на ОБЕМА, % разлика) + зелен ден -
    #     ЧИСТО обемно измерение (само нивото на обема, без цена в
    #     самата формула), различно от OBV/PVT (кумулативни, с посока) и
    #     volspike (само днешния обем срещу среден) - 2 прага = 2.
    vol_sma_fast = vol.rolling(5).mean()
    vol_sma_slow = vol.rolling(20).mean()
    vol_osc = (vol_sma_fast - vol_sma_slow) / vol_sma_slow * 100
    for thresh in (0, 20):
        s = (vol_osc.shift(1) <= thresh) & (vol_osc > thresh) & (close > close.shift(1))
        sig[f"volosc_t{thresh}"] = s.fillna(False).to_numpy()

    # 53) "Morning star" - 3-дневна свещна РЕВЕРСАЛ формация (ден1 голям
    #     червен, ден2 малко тяло/"звезда", ден3 голям зелен затварящ над
    #     средата на ден1 - МНОЖЕСТВЕНА формация, различна от engulfing/
    #     hammer/doji/threewhitesoldiers) - 2 толеранса за "колко малка
    #     трябва да е звездата" = 2.
    body1_ms = close.shift(2) - open_.shift(2)
    body2_ms = (close.shift(1) - open_.shift(1)).abs()
    range1_ms = high.shift(2) - low.shift(2)
    body3_ms = close - open_
    day1_red = body1_ms < 0
    day3_green = body3_ms > 0
    close_above_mid1 = close > (open_.shift(2) + close.shift(2)) / 2
    for tol in (0.3, 0.5):
        day2_small = body2_ms <= tol * range1_ms
        s = day1_red & day2_small & day3_green & close_above_mid1
        sig[f"morningstar_t{tol}"] = s.fillna(False).to_numpy()

    # 54) Donchian "width squeeze" пробив - ШИРИНАТА на N-дневния high/low
    #     канал е в долния 20-ти персентил от последните 60 дни (ниска
    #     волатилност ПО ОБХВАТ на канала), после пробив над върха -
    #     различна база от Bollinger squeeze #9 (std-базиран) и ATR
    #     expand #33 (обратна посока, растеж) - 2 прозореца = 2.
    for w in (20, 40):
        high_max_sq = high.rolling(w).max()
        low_min_sq = low.rolling(w).min()
        width_sq = (high_max_sq - low_min_sq) / low_min_sq
        squeeze_sq = width_sq <= width_sq.rolling(60).quantile(0.20)
        s = squeeze_sq.shift(1) & (close > high_max_sq.shift(1))
        sig[f"donchsqueeze_w{w}"] = s.fillna(False).to_numpy()

    # 55) EMA кросоувър (fast/slow ЕКСПОНЕНЦИАЛНИ средни, не SMA като
    #     macross #8 - различно тегло на скорошните дни, различна
    #     "скорост" на реакция) - 2 комплекта периоди = 2.
    for f, s_ in ((8, 21), (13, 34)):
        ema_f_c = close.ewm(span=f, adjust=False).mean()
        ema_s_c = close.ewm(span=s_, adjust=False).mean()
        sgnl = (ema_f_c.shift(1) <= ema_s_c.shift(1)) & (ema_f_c > ema_s_c)
        sig[f"ema_cross_f{f}_s{s_}"] = sgnl.fillna(False).to_numpy()

    # 56) OBV "бичи дивергенция" - цената е близо до своето N-дневно дъно,
    #     НО OBV (#11) е ЯСНО над своето собствено N-дневно дъно (нормализирано
    #     спрямо собствения си диапазон, защото OBV е НЕОГРАНИЧЕН/мащабно-
    #     зависим за разлика от RSI 0-100) - аналогично на rsi_bulldiv #46,
    #     но с ОБЕМЕН инструмент вместо осцилатор - 2 прозореца = 2.
    for w in (10, 20):
        roll_low_price_obv = close.rolling(w).min()
        roll_low_obv = obv.rolling(w).min()
        obv_range = (obv.rolling(w).max() - roll_low_obv).replace(0, np.nan)
        near_price_low_obv = close <= roll_low_price_obv * 1.01
        obv_elevated = (obv - roll_low_obv) >= 0.3 * obv_range
        s = near_price_low_obv & obv_elevated & (close > close.shift(1))
        sig[f"obv_bulldiv_w{w}"] = s.fillna(False).to_numpy()

    # 57) Keltner MIDLINE пробив - цена пресича ЦЕНТРАЛНАТА EMA на Keltner
    #     канала (различна точка на пробив от Keltner #20, който изисква
    #     пробив над ГОРНАТА лента; различна линия от VWAP reclaim #24,
    #     защото е EMA на цената, не обемно претеглена) - 2 периода = 2.
    for p in (14, 20):
        ema_center_mid = close.ewm(span=p, adjust=False).mean()
        s = (close.shift(1) <= ema_center_mid.shift(1)) & (close > ema_center_mid)
        sig[f"keltnermid_p{p}"] = s.fillna(False).to_numpy()

    # 58) Acceleration Bands (Price Headley) пробив - горна лента =
    #     SMA(high*(1+4*(high-low)/(high+low))) - специфична волатилност-
    #     разширяваща формула, различна от Bollinger/Keltner/ATR expand - 2
    #     периода = 2.
    ab_up = high * (1 + 4 * (high - low) / (high + low))
    for p in (10, 20):
        upper_band_sma = ab_up.rolling(p).mean()
        s = (close.shift(1) <= upper_band_sma.shift(1)) & (close > upper_band_sma)
        sig[f"accelband_p{p}"] = s.fillna(False).to_numpy()

    # === КРЪГ 7 (03.11, по изрична молба "дай напълно други стратегии
    # различни от тези") - 10 НАПЪЛНО различни семейства, 20 нови варианта.
    # За разлика от кръговете 1-6 (всички чисти ТЕХНИЧЕСКИ индикатори -
    # цена/обем/moving average производни), тук НАРОЧНО излизаме извън тази
    # "школа": календарни ефекти (БЕЗ цена/обем изобщо), статистическо
    # mean-reversion (z-score, не bounded 0-100 осцилатор), психологически
    # кръгли нива, корелационна статистика цена-обем, тренд КАНАЛ фитнат с
    # регресия (не moving average basis), "anchored" VWAP от ДИНАМИЧЕН swing
    # anchor (не rolling прозорец с ФИКСИРАНА дължина), multi-leg ценова
    # ФОРМАЦИЯ (volatility contraction), и дълго-прозоречен "база + тих обем"
    # пробив (Weinstein Stage 2 стил).

    # 49) Календарен ден-от-седмицата ефект - ЕДИНСТВЕНОТО тук семейство,
    #     което НЕ ползва цена/обем/индикатор ИЗОБЩО, само датата (класически
    #     "ден на седмицата" пазарен ефект от количествени изследвания) -
    #     понеделник/петък = 2.
    dow = pd.Series(df.index.dayofweek, index=df.index)
    sig["calendar_monday"] = (dow == 0).to_numpy()
    sig["calendar_friday"] = (dow == 4).to_numpy()

    # 50) Календарен начало/край на месеца ефект ("turn of the month" -
    #     известен сезонен ефект, пак БЕЗ цена/обем) - 2.
    day_of_month = pd.Series(df.index.day, index=df.index)
    days_in_month = pd.Series(df.index.days_in_month, index=df.index)
    sig["calendar_monthstart"] = (day_of_month <= 3).to_numpy()
    sig["calendar_monthend"] = (day_of_month >= days_in_month - 2).to_numpy()

    # 51) Z-score mean-reversion отскок - цената е ДЪЛБОКО под своята
    #     N-дневна средна (измерено в СТАНДАРТНИ ОТКЛОНЕНИЯ, статистическа
    #     мярка) - различно от RSI/CCI/Stochastic/Williams/MFI (всички
    #     bounded 0-100(ish) осцилатори с различни формули, не директно
    #     разстояние в std) - 2 прага = 2.
    ma_z = close.rolling(20).mean()
    std_z = close.rolling(20).std()
    zscore = (close - ma_z) / std_z
    for k in (2.0, 3.0):
        s = (zscore.shift(1) <= -k) & (close > close.shift(1))
        sig[f"zscore_bounce_k{k}"] = s.fillna(False).to_numpy()

    # 52) "Accumulation" серия - N последователни дни, в които ЗАТВАРЯНЕТО
    #     е в горните 30% от ДНЕВНИЯ диапазон (close близо до high на деня,
    #     не отношение open/close като свещните формации #15/34/35/53) - 2
    #     дължини = 2.
    close_pos_in_range = ((close - low) / (high - low)).fillna(0.5)
    strong_close = close_pos_in_range >= 0.7
    streak3 = strong_close & strong_close.shift(1) & strong_close.shift(2)
    sig["accum_streak_n3"] = streak3.fillna(False).to_numpy()
    streak5 = streak3 & strong_close.shift(3) & strong_close.shift(4)
    sig["accum_streak_n5"] = streak5.fillna(False).to_numpy()

    # 53) Цена-обем КОРЕЛАЦИЯ (Pearson коефициент между дневната % промяна
    #     и обема през rolling прозорец) обръща от <=0 към >0 - статистическа
    #     мярка, различна от ВСИЧКО досегашно (OBV/PVT/CMF тежат ЗНАКА или
    #     величината директно, не изчисляват коефициент на корелация) - 2
    #     прозореца = 2.
    ret1 = close.pct_change()
    for w in (10, 20):
        corr = ret1.rolling(w).corr(vol)
        s = (corr.shift(1) <= 0) & (corr > 0)
        sig[f"pv_corr_w{w}"] = s.fillna(False).to_numpy()

    # 54) Регресионен тренд-канал пробив - ГОРНА лента = OLS права (най-малки
    #     квадрати) ПРЕЗ прозореца + k*std на РЕЗИДУАЛИТЕ - различен "котва"
    #     от Donchian (min/max), Bollinger (SMA+std НА ЦЕНАТА), и Keltner
    #     (EMA+ATR) - тук центърът е ФИТНАТА ПРАВА, не пълзяща средна - 2
    #     прозореца = 2.
    def _regression_channel_upper(series: pd.Series, window: int, k: float) -> pd.Series:
        x = np.arange(window, dtype=float)
        x_mean = x.mean()
        x_var = ((x - x_mean) ** 2).sum()

        def _calc(y):
            slope = ((x - x_mean) * (y - y.mean())).sum() / x_var
            intercept = y.mean() - slope * x_mean
            fitted = intercept + slope * x
            resid_std = (y - fitted).std()
            return float(fitted[-1] + k * resid_std)

        return series.rolling(window).apply(_calc, raw=True)

    for w in (20, 40):
        upper_channel = _regression_channel_upper(close, w, 2.0)
        s = (close.shift(1) <= upper_channel.shift(1)) & (close > upper_channel)
        sig[f"regchannel_w{w}"] = s.fillna(False).to_numpy()

    # 55) "Anchored" VWAP - анкерът е ДИНАМИЧЕН (индексът на най-ниското low
    #     през последните lookback дни), VWAP се смята КУМУЛАТИВНО от ТОЗИ
    #     анкер насам (РАЗШИРЯВАЩ се прозорец от swing-low точка, не ФИКСИРАН
    #     rolling прозорец като vwap_reclaim #24) - ТРЕТОТО тук stateful/
    #     итеративно изчисление (виж _anchored_vwap_flip по-долу) - 2
    #     lookback прозореца = 2.
    for lb in (20, 40):
        sig[f"anchvwap_lb{lb}"] = _anchored_vwap_flip(
            low.to_numpy(), typical_price.to_numpy(), vol.to_numpy(), close.to_numpy(), lb,
        )

    # 56) "Кръгли числа" психологически пробив - цена пресича най-близкото
    #     цяло/половин число НАД вчерашното затваряне (психологическа
    #     подкрепа/съпротива, НУЛЕВА статистика/индикатор - просто
    #     аритметика на нивото на цената) - цяло число + половинка = 2.
    whole_level = np.floor(close.shift(1)) + 1
    sig["roundnum_whole"] = ((close.shift(1) < whole_level) & (close >= whole_level)).fillna(False).to_numpy()
    half_level = (np.floor(close.shift(1) * 2) + 1) / 2
    sig["roundnum_half"] = ((close.shift(1) < half_level) & (close >= half_level)).fillna(False).to_numpy()

    # 57) Volatility Contraction Pattern (VCP, Minervini стил) - 3
    #     последователни "крака" от по L дни, всеки със ПО-МАЛЪК % обхват от
    #     предишния (свиващи се pullback-и), после пробив над целия 3L-дневен
    #     връх - МНОЖЕСТВЕН ценов ФОРМАЦИОНЕН патърн (3 отделни "крака"), за
    #     разлика от threebar_tight #16 (само 3 дни) или bbsqueeze/donchsqueeze
    #     (единична мярка за волатилност, не отделни крака) - 2 дължини крак = 2.
    for leg_l in (10, 15):
        def _leg_range(shift_days):
            h_leg = high.shift(shift_days).rolling(leg_l).max()
            l_leg = low.shift(shift_days).rolling(leg_l).min()
            return (h_leg - l_leg) / l_leg

        leg3 = _leg_range(0)
        leg2 = _leg_range(leg_l)
        leg1 = _leg_range(2 * leg_l)
        contracting = (leg3 < leg2) & (leg2 < leg1)
        overall_high_prior = high.shift(1).rolling(3 * leg_l).max()
        s = contracting & (close > overall_high_prior)
        sig[f"vcp_L{leg_l}"] = s.fillna(False).to_numpy()

    # 58) "Stage 2" база + тих обем пробив (Weinstein стил) - цена близо до
    #     ДЪЛГО-прозоречен връх (100/150 дни - МНОГО по-дълъг от donch_h
    #     максимум 55), ПРЕДХОЖДАНА от обем ПОД средния (тиха база, не
    #     обемен скок като volspike/nearhigh) - различна комбинация
    #     "ниво + обемен режим" от всичко досегашно - 2 прозореца = 2.
    for w in (100, 150):
        long_high = high.rolling(w).max().shift(1)
        vol_recent = vol.rolling(10).mean()
        vol_base = vol.rolling(40).mean()
        quiet = (vol_recent < vol_base * 0.8).shift(1)
        near_high = close.shift(1) >= long_high * 0.95
        s = quiet & near_high & (close > long_high)
        sig[f"stage2_w{w}"] = s.fillna(False).to_numpy()

    # === КРЪГ 8 (04.11, по молба "давай още стратегии") - 9 НОВИ
    # механично различни семейства, 18 нови варианта. Виж горния docstring
    # КРЪГ 8 за защо TTM Squeeze/Ichimoku/Key-reversal НЕ са включени тук
    # (вече тествани и/или refuted в strategy_backtest.py/strategies.py).

    # 59) Chandelier Exit бичи flip (виж _chandelier_exit_flip по-горе) -
    #     ЧЕТВЪРТОТО stateful/итеративно изчисление тук (покрай PSAR #25,
    #     Supertrend #47, Anchored VWAP #55) - стоп-линия анкерирана към
    #     rolling highest-high/lowest-low (не към (H+L)/2 всеки ден като
    #     Supertrend) - 2 (период, множител) комбинации = 2.
    for length_ch, mult_ch in ((22, 3.0), (10, 2.0)):
        highest_high_ch = high.rolling(length_ch).max().to_numpy()
        lowest_low_ch = low.rolling(length_ch).min().to_numpy()
        atr_ch = tr_kc.ewm(alpha=1 / length_ch, adjust=False).mean().to_numpy()
        sig[f"chandelier_l{length_ch}_m{mult_ch}"] = _chandelier_exit_flip(
            highest_high_ch, lowest_low_ch, close.to_numpy(), atr_ch, mult_ch,
        )

    # 60) Negative Volume Index (NVI) нов връх пробив - кумулативен индекс,
    #     който се ОБНОВЯВА САМО в дни с ПО-НИСЪК обем от вчера ("тиха"
    #     акумулация, хипотеза за "умни пари" на нисък обем) - ОБРАТНА
    #     логика от OBV #11/PVT #32 (те тежат ВСЕКИ ден, без оглед на
    #     обемния РЕЖИМ спрямо вчера) - 2 прозореца = 2.
    ret_pct_nvi = close.pct_change()
    quiet_day_nvi = vol < vol.shift(1)
    nvi_step = ret_pct_nvi.where(quiet_day_nvi, 0.0).fillna(0.0)
    nvi = 1000.0 * (1.0 + nvi_step).cumprod()
    for w in (20, 40):
        nvi_roll_max = nvi.rolling(w).max().shift(1)
        s = (nvi > nvi_roll_max) & (close > close.shift(1))
        sig[f"nvi_newhigh_w{w}"] = s.fillna(False).to_numpy()

    # 61) Coppock Curve нулева линия обрат - СУМА от ДВЕ ROC (различни
    #     периоди), изгладена с ЛИНЕЙНО-претеглена MA (WMA, не EMA като
    #     MACD #12/TRIX #30, и не проста SMA) - различна "агрегация" от
    #     всичко momentum-базирано досега - 2 WMA прозореца (стандартен +
    #     по-чувствителен) = 2.
    roc_long_cc = close.pct_change(14) * 100
    roc_short_cc = close.pct_change(11) * 100
    sum_roc_cc = roc_long_cc + roc_short_cc

    def _wma(series: pd.Series, window: int) -> pd.Series:
        weights = np.arange(1, window + 1, dtype=float)
        return series.rolling(window).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    for wma_w in (10, 6):
        coppock = _wma(sum_roc_cc, wma_w)
        s = (coppock.shift(1) <= 0) & (coppock > 0)
        sig[f"coppock_w{wma_w}"] = s.fillna(False).to_numpy()

    # 62) Bollinger %B отскок от ДОЛНАТА лента - ПОЗИЦИЯТА на цената В
    #     рамките на лентите (0=долна, 1=горна), пресичаща 0 нагоре -
    #     различна ТОЧКА на пробив от bbsqueeze #9/donchsqueeze #54 (там е
    #     ГОРНАТА лента, след squeeze) - 2 k-множителя = 2.
    ma_pb = close.rolling(20).mean()
    std_pb = close.rolling(20).std()
    for k in (2.0, 2.5):
        upper_pb = ma_pb + k * std_pb
        lower_pb = ma_pb - k * std_pb
        percent_b = (close - lower_pb) / (upper_pb - lower_pb)
        s = (percent_b.shift(1) <= 0) & (percent_b > 0)
        sig[f"bbpercentb_k{k}"] = s.fillna(False).to_numpy()

    # 63) Bollinger Band "walk" - N ПОСЛЕДОВАТЕЛНИ затваряния НАД горната
    #     лента (continuation сила ЧРЕЗ брой поредни дни, не единичен
    #     пробив-кросоувър като bbsqueeze/%B реклейм #62) - 2 дължини = 2.
    above_upper_walk = close > (ma_pb + 2.0 * std_pb)
    sig["bbwalk_n2"] = (above_upper_walk & above_upper_walk.shift(1)).fillna(False).to_numpy()
    sig["bbwalk_n3"] = (above_upper_walk & above_upper_walk.shift(1) & above_upper_walk.shift(2)).fillna(False).to_numpy()

    # 64) Williams Alligator (Bill Williams) бичи "уста отворена" - ТРИ
    #     ИЗМЕСТЕНИ/изгладени (SMMA) средни - jaw/teeth/lips, с РАЗЛИЧНИ
    #     периоди И различни измествания напред - различна конструкция от
    #     всеки MA кросоувър досега (macross #8/ema_cross #55 нямат
    #     изместване) - стриктно подреждане ("отворена уста") + по-мек
    #     крос вариант = 2.
    jaw_al = close.ewm(alpha=1 / 13, adjust=False).mean().shift(8)
    teeth_al = close.ewm(alpha=1 / 8, adjust=False).mean().shift(5)
    lips_al = close.ewm(alpha=1 / 5, adjust=False).mean().shift(3)
    strict_al = (jaw_al < teeth_al) & (teeth_al < lips_al) & (close > lips_al)
    sig["alligator_strict"] = strict_al.fillna(False).to_numpy()
    loose_al = (close.shift(1) <= lips_al.shift(1)) & (close > lips_al) & (teeth_al > jaw_al)
    sig["alligator_loose"] = loose_al.fillna(False).to_numpy()

    # 65) Сезонен "turn-of-year"/"January effect" прозорец - известен
    #     (количествено документиран) сезонен ефект СПЕЦИФИЧНО за малки/
    #     спекулативни акции - РАЗШИРЯВА календарната логика от кръг 7
    #     (ден-от-седмицата/начало-край на месец) към ГОДИШЕН сезонен
    #     прозорец - пак БЕЗ цена/обем изобщо - тесен прозорец (15.12-
    #     15.01) + по-широк "исторически силни месеци" (ное-дек-яну) = 2.
    month_seas = pd.Series(df.index.month, index=df.index)
    day_seas = pd.Series(df.index.day, index=df.index)
    sig["calendar_turnofyear"] = (
        ((month_seas == 12) & (day_seas >= 15)) | ((month_seas == 1) & (day_seas <= 15))
    ).to_numpy()
    sig["calendar_strongmonths"] = month_seas.isin([11, 12, 1]).to_numpy()

    # 66) Предпразничен/следпразничен "drift" - РЕАЛЕН US federal holiday
    #     календар (_HOLIDAY_CBD на module level, виж горе) - не аритметика
    #     на датата като #65 - ден ПРЕДИ празник / ден СЛЕД празник = 2.
    next_bday_plain_hol = df.index + BDay(1)
    next_bday_holiday_hol = df.index + _HOLIDAY_CBD
    sig["calendar_pre_holiday"] = np.asarray(next_bday_holiday_hol > next_bday_plain_hol)
    prev_bday_plain_hol = df.index - BDay(1)
    prev_bday_holiday_hol = df.index - _HOLIDAY_CBD
    sig["calendar_post_holiday"] = np.asarray(prev_bday_holiday_hol < prev_bday_plain_hol)

    # 67) Stochastic RSI oversold завой - Stochastic ФОРМУЛАТА (позиция в
    #     диапазон), приложена към САМИЯ RSI (не към цената като Stochastic
    #     #13, и не bounded директно като RSI #5) - "вложен" осцилатор,
    #     различна конструкция от всичко досегашно - 2 периода = 2.
    rsi14_srsi = _rsi(close, 14)
    for p in (14, 20):
        rsi_min_srsi = rsi14_srsi.rolling(p).min()
        rsi_max_srsi = rsi14_srsi.rolling(p).max()
        stoch_rsi = (rsi14_srsi - rsi_min_srsi) / (rsi_max_srsi - rsi_min_srsi) * 100
        s = (stoch_rsi.shift(1) <= 20) & (stoch_rsi > 20)
        sig[f"stochrsi_p{p}"] = s.fillna(False).to_numpy()

    # === КРЪГ 9 (04.11, по молба "продължаваме") - 8 НОВИ механично
    # различни семейства, 16 нови варианта (303 единични общо). Проверени
    # предварително срещу strategies.py каталога (73 имена) - никое от
    # следните не е вече тествано там.

    # 68) Williams Fractal пробив - 5-бар (или 3-бар, по-мек вариант)
    #     ГЕОМЕТРИЧНА swing-high ФОРМАЦИЯ (връхът е строго НАЙ-ВИСОК измежду
    #     съседите си от двете страни, потвърдена с 2-дневно/1-дневно
    #     закъснение) - различна конструкция от NR7/inside-bar/VCP (тях
    #     определя обхват/контракция, не локален екстремум) - 2 варианта
    #     (стриктен 2-бар + мек 1-бар) = 2. ЧЕСТНА бележка: нивото на
    #     "резистънса" е СТЪПКОВИДНА функция (сменя се само при нов
    #     потвърден фрактал), не непрекъснато преизчисляваща се като
    #     Donchian - затова денят, в който самото ниво "прескача", може
    #     рядко да изглежда като фалшив пробив.
    is_fractal2 = (high.shift(2) > high.shift(4)) & (high.shift(2) > high.shift(3)) & (high.shift(2) > high.shift(1)) & (high.shift(2) > high)
    fractal_level2 = high.shift(2).where(is_fractal2).ffill()
    s = (close.shift(1) <= fractal_level2.shift(1)) & (close > fractal_level2)
    sig["fractal_breakout_n2"] = s.fillna(False).to_numpy()
    is_fractal1 = (high.shift(1) > high.shift(2)) & (high.shift(1) > high)
    fractal_level1 = high.shift(1).where(is_fractal1).ffill()
    s = (close.shift(1) <= fractal_level1.shift(1)) & (close > fractal_level1)
    sig["fractal_breakout_n1"] = s.fillna(False).to_numpy()

    # 69) VWAP Bands пробив - ЛЕНТИ (± k*std на отклонението цена-VWAP)
    #     АНКЕРИРАНИ към VWAP линията (различна "котва" от Bollinger #9
    #     (SMA на цената) и Keltner #20 (EMA+ATR) - тук центърът е
    #     обемно-претеглена средна, а ширината е от СОБСТВЕНОТО отклонение
    #     от нея, не от ATR/std на самата цена) - 2 k-множителя = 2.
    vwap_vb = (typical_price * vol).rolling(20).sum() / vol.rolling(20).sum()
    dev_vb = typical_price - vwap_vb
    std_vb = dev_vb.rolling(20).std()
    for k in (2.0, 1.5):
        upper_vb = vwap_vb + k * std_vb
        s = (close.shift(1) <= upper_vb.shift(1)) & (close > upper_vb)
        sig[f"vwapband_w20_k{k}"] = s.fillna(False).to_numpy()

    # 70) Относителен обем ПЕРЦЕНТИЛЕН ранг скок - ПРОЦЕНТИЛНА позиция на
    #     днешния обем спрямо последните w дни (устойчива на екстремни
    #     outlier-и статистика) - различна МЯРКА от volspike #3 (отношение
    #     към СРЕДНОТО) и volosc #52 (разлика на fast/slow SMA) - 2 прага = 2.
    def _vol_percentile_rank(window_vals: np.ndarray) -> float:
        return float((window_vals <= window_vals[-1]).mean())

    vol_rank = vol.rolling(20).apply(_vol_percentile_rank, raw=True)
    for q in (0.9, 0.95):
        s = (vol_rank >= q) & (close > close.shift(1))
        sig[f"relvolrank_w20_q{q}"] = s.fillna(False).to_numpy()

    # 71) Ehlers Fisher Transform обрат - НЕЛИНЕЕН (arctanh-подобен)
    #     трансформ на нормализираната позиция на цената в N-дневния
    #     high/low диапазон - различна МАТЕМАТИКА от всичко осцилаторно
    #     досега (Stochastic/CCI/Williams%R/MFI са bounded РАЦИОНАЛНИ
    #     формули, не логаритмичен трансформ) - 2 прозореца = 2. ЧЕСТНА
    #     бележка: класическата формула изглажда СУРОВАТА позиция с
    #     рекурсивна EMA(0.33/0.67) ПРЕДИ трансформа - тук е заменена с
    #     обикновена ewm(span=5) (вектор ризирано приближение, не точно
    #     същата рекурсия, но същия дух на изглаждане).
    for w in (10, 20):
        hh_f = high.rolling(w).max()
        ll_f = low.rolling(w).min()
        raw_f = (2 * ((close - ll_f) / (hh_f - ll_f) - 0.5)).clip(-0.999, 0.999)
        smoothed_f = raw_f.ewm(span=5, adjust=False).mean().clip(-0.999, 0.999)
        fisher = 0.5 * np.log((1 + smoothed_f) / (1 - smoothed_f))
        s = (fisher.shift(1) <= fisher.shift(2)) & (fisher > fisher.shift(1)) & (fisher.shift(1) < -1)
        sig[f"fisher_turn_w{w}"] = s.fillna(False).to_numpy()

    # 72) Guppy Multiple Moving Average (GMMA) "ribbon" кросоувър - СРЕДНО
    #     от 6 КРАТКОСРОЧНИ EMA (3/5/8/10/12/15) пресича СРЕДНОТО от 6
    #     ДЪЛГОСРОЧНИ EMA (30/35/40/45/50/60) - различна СТРУКТУРА от всеки
    #     2-EMA кросоувър досега (macross #8/ema_cross #55 ползват по 2
    #     средни, не 2 ГРУПИ от по 6) - чист крос + вариант, изискващ
    #     предходно "свиване" на ribbon-а (двете групи били близо, т.е.
    #     ниска волатилност ПРЕДИ разтварянето) = 2.
    short_avg_gm = sum(close.ewm(span=p, adjust=False).mean() for p in (3, 5, 8, 10, 12, 15)) / 6
    long_avg_gm = sum(close.ewm(span=p, adjust=False).mean() for p in (30, 35, 40, 45, 50, 60)) / 6
    cross_gm = (short_avg_gm.shift(1) <= long_avg_gm.shift(1)) & (short_avg_gm > long_avg_gm)
    sig["gmma_cross_plain"] = cross_gm.fillna(False).to_numpy()
    spread_gm = (short_avg_gm - long_avg_gm).abs() / long_avg_gm
    was_compressed_gm = spread_gm.shift(1) <= spread_gm.rolling(60).quantile(0.25)
    sig["gmma_cross_compressed"] = (cross_gm & was_compressed_gm).fillna(False).to_numpy()

    # 73) Relative Vigor Index (RVI) обрат - съотношение на СРЕДНОТО
    #     "тяло" (close-open) към СРЕДНИЯ дневен диапазон (high-low) през
    #     прозорец, срещу претеглена 4-бар "сигнална" линия - различна
    #     формула от Elder Force #19/Bull Power #38 (там е РАЗЛИКА/EMA на
    #     суровата промяна, не отношение тяло/диапазон усреднени отделно) -
    #     2 периода = 2.
    for p in (10, 14):
        rvi_num = (close - open_).rolling(p).mean()
        rvi_den = (high - low).rolling(p).mean()
        rvi = rvi_num / rvi_den
        rvi_sig = (rvi + 2 * rvi.shift(1) + 2 * rvi.shift(2) + rvi.shift(3)) / 6
        s = (rvi.shift(1) <= rvi_sig.shift(1)) & (rvi > rvi_sig)
        sig[f"rvi_turn_p{p}"] = s.fillna(False).to_numpy()

    # 74) McGinley Dynamic кросоувър (виж _mcginley_dynamic по-горе) -
    #     ПЕТОТО stateful/итеративно изчисление тук (покрай PSAR, Supertrend,
    #     Anchored VWAP, Chandelier Exit) - единствената АДАПТИВНА-по-
    #     скорост средна тук (скоростта зависи от текущото съотношение
    #     цена/MD, не фиксиран период/alpha като всичко останало) - 2
    #     константи (N) = 2.
    for n_mg in (10, 20):
        md_arr = _mcginley_dynamic(close.to_numpy(), float(n_mg))
        md_series = pd.Series(md_arr, index=df.index)
        s = (close.shift(1) <= md_series.shift(1)) & (close > md_series)
        sig[f"mcginley_n{n_mg}"] = s.fillna(False).to_numpy()

    # 75) Percentage Price Oscillator (PPO) обрат - СЪЩАТА EMA-разлика
    #     конструкция като MACD #12, но изразена като ПРОЦЕНТ от бавната
    #     EMA (не абсолютна $ разлика) - прави сигнала МАЩАБНО-независим
    #     (penny stocks с цена $0.50 и $9 иначе имат несравними абсолютни
    #     MACD стойности) - 2 комплекта периоди (същите като MACD #12, за
    #     директно сравнение разлика абсолютно/процентно) = 2.
    for fast, slow in ((12, 26), (8, 17)):
        ema_f_ppo = close.ewm(span=fast, adjust=False).mean()
        ema_s_ppo = close.ewm(span=slow, adjust=False).mean()
        ppo = (ema_f_ppo - ema_s_ppo) / ema_s_ppo * 100
        ppo_sig = ppo.ewm(span=9, adjust=False).mean()
        s = (ppo.shift(1) <= ppo_sig.shift(1)) & (ppo > ppo_sig)
        sig[f"ppo_f{fast}_s{slow}"] = s.fillna(False).to_numpy()

    # === КРЪГ 10 (04.11, по молба "10") - 8 НОВИ механично различни
    # семейства, 16 нови варианта (319 единични общо). Пак проверени
    # предварително срещу strategies.py каталога за да няма дублиране.

    # 76) Vortex Indicator (VI+/VI-) кросоувър - ДВИЖЕНИЕ, измерено като
    #     абсолютно разстояние high-спрямо-предишен-low / low-спрямо-
    #     предишен-high (различна конструкция от +DI/-DI в ADX #14, което
    #     гледа ЗНАКА на up_move/down_move, не абсолютно разстояние спрямо
    #     ПРОТИВОПОЛОЖНАТА цена отпреди) - 2 периода = 2.
    vm_plus_vi = (high - low.shift(1)).abs()
    vm_minus_vi = (low - high.shift(1)).abs()
    for p in (14, 21):
        vi_plus = vm_plus_vi.rolling(p).sum() / tr_kc.rolling(p).sum()
        vi_minus = vm_minus_vi.rolling(p).sum() / tr_kc.rolling(p).sum()
        s = (vi_plus.shift(1) <= vi_minus.shift(1)) & (vi_plus > vi_minus)
        sig[f"vortex_p{p}"] = s.fillna(False).to_numpy()

    # 77) Mass Index "reversal bulge" (Dorsey/Bulkowski) - ДВОЙНО EMA-
    #     изгладено съотношение дневен-диапазон/изгладен-диапазон, сумирано
    #     през 25 дни - мери ЕКСПАНЗИЯ на волатилността (различно от
    #     ATR expand #33, bbsqueeze/donchsqueeze - тук е СУМА от съотношение,
    #     не директно ниво/персентил) - сигнал при "bulge" (докоснал >=27,
    #     после пада <26.5 - класически reversal trigger) - 2 прозореца
    #     (класически 25 + по-бърз 15) = 2.
    range_mi = high - low
    ema9_range_mi = range_mi.ewm(span=9, adjust=False).mean()
    ema9ema9_range_mi = ema9_range_mi.ewm(span=9, adjust=False).mean()
    ratio_mi = ema9_range_mi / ema9ema9_range_mi
    for w in (25, 15):
        mass_index = ratio_mi.rolling(w).sum()
        touched_27 = mass_index.rolling(10).max() >= 27
        s = touched_27.shift(1) & (mass_index.shift(1) >= 26.5) & (mass_index < 26.5)
        sig[f"massindex_w{w}"] = s.fillna(False).to_numpy()

    # 78) Ease of Movement (EMV) обрат - комбинира ПРОМЯНАТА в средната
    #     точка high/low С обема (различна комбинация от OBV/PVT/CMF/MFI/
    #     NVI - те всички тежат ПОСОКАТА/ВЕЛИЧИНАТА на ЦЕНОВАТА промяна с
    #     обема, тук е "лекота на движение" - малко обем за голямо
    #     разстояние = високо EMV) - 2 периода на изглаждащата SMA = 2.
    midpoint_change_emv = (high + low) / 2 - (high.shift(1) + low.shift(1)) / 2
    emv_raw = midpoint_change_emv * (high - low) / vol.replace(0, np.nan)
    for p in (14, 20):
        emv_sma = emv_raw.rolling(p).mean()
        s = (emv_sma.shift(1) <= 0) & (emv_sma > 0)
        sig[f"emv_p{p}"] = s.fillna(False).to_numpy()

    # 79) True Strength Index (TSI) обрат - ДВОЙНО EMA-изгладена (не
    #     единично като CMO #39, не Wilder-изгладена като RSI #5) разлика
    #     на цената, нормализирана от двойно EMA-изгладена АБСОЛЮТНА
    #     разлика - различна "дълбочина" на изглаждане от всичко
    #     осцилаторно досега - 2 комплекта периоди = 2.
    diff_tsi = close.diff()
    for long_p, short_p in ((13, 7), (25, 13)):
        ema1_tsi = diff_tsi.ewm(span=long_p, adjust=False).mean()
        ema2_tsi = ema1_tsi.ewm(span=short_p, adjust=False).mean()
        abs_ema1_tsi = diff_tsi.abs().ewm(span=long_p, adjust=False).mean()
        abs_ema2_tsi = abs_ema1_tsi.ewm(span=short_p, adjust=False).mean()
        tsi = 100 * ema2_tsi / abs_ema2_tsi
        s = (tsi.shift(1) <= 0) & (tsi > 0)
        sig[f"tsi_l{long_p}_s{short_p}"] = s.fillna(False).to_numpy()

    # 80) Detrended Price Oscillator (DPO) обрат - сравнява ЗАТВАРЯНЕ ОТ
    #     МИНАЛОТО (изместено назад с p/2+1 дни) СРЕЩУ ТЕКУЩАТА rolling
    #     средна - нарочно ПРЕМАХВА тренда, за да изолира КРАТКОСРОЧНИЯ
    #     цикъл (различна конструкция от ВСИЧКО тук - никое друго семейство
    #     не сравнява МИНАЛА цена срещу ТЕКУЩА средна) - 2 периода = 2.
    for p in (20, 14):
        shift_amt_dpo = p // 2 + 1
        sma_dpo = close.rolling(p).mean()
        dpo = close.shift(shift_amt_dpo) - sma_dpo
        s = (dpo.shift(1) <= 0) & (dpo > 0)
        sig[f"dpo_p{p}"] = s.fillna(False).to_numpy()

    # 81) OBV Oscillator - OBV #11 пресича СОБСТВЕНАТА си rolling средна
    #     (прилага класическата MA-кросоувър МЕХАНИКА #8/#55 към ОБЕМЕН
    #     индикатор вместо към цената - същия дух като Stochastic RSI #67,
    #     което приложи Stochastic към RSI) - 2 прозореца = 2.
    for w in (10, 20):
        obv_sma = obv.rolling(w).mean()
        s = (obv.shift(1) <= obv_sma.shift(1)) & (obv > obv_sma)
        sig[f"obvosc_w{w}"] = s.fillna(False).to_numpy()

    # 82) Pivot Point ПОДКРЕПА отскок - ОГЛЕДАЛНО на pivot_r1/r2 #42
    #     (там е пробив НАД съпротива, тук е ОТСКОК от подкрепа S1/S2 -
    #     различна СТРУКТУРА на сигнала - reversal вместо continuation,
    #     върху СЪЩАТА floor-trader геометрична формула) - 2 нива = 2.
    s1_pp = 2 * pivot_pp - prior_high_pp
    s2_pp = pivot_pp - (prior_high_pp - prior_low_pp)
    sig["pivot_s1_bounce"] = ((low.shift(1) <= s1_pp) & (close > s1_pp) & (close > close.shift(1))).fillna(False).to_numpy()
    sig["pivot_s2_bounce"] = ((low.shift(1) <= s2_pp) & (close > s2_pp) & (close > close.shift(1))).fillna(False).to_numpy()

    # 83) Chande Forecast Oscillator (CFO) обрат - ПРОЦЕНТНО отклонение на
    #     цената от своята OLS регресионна ПРОГНОЗА (преизползва
    #     _regression_channel_upper #54 с k=0 - чист fitted endpoint, без
    #     band отместване) - различна УПОТРЕБА от regchannel #54 (там е
    #     band-пробив, тук е ОСЦИЛАТОР около нулата) - 2 прозореца = 2.
    for p in (20, 10):
        forecast_cfo = _regression_channel_upper(close, p, 0.0)
        cfo = (close - forecast_cfo) / close * 100
        s = (cfo.shift(1) <= 0) & (cfo > 0)
        sig[f"cfo_p{p}"] = s.fillna(False).to_numpy()

    # === КРЪГ 11 (04.11, по изрична молба "напълно нови 25 стратегии") -
    # 12 НОВИ механично различни семейства, 25 нови варианта. Проверени
    # предварително срещу strategies.py каталога (grep за "hull|vzo|ulcer|
    # qstick|harami|sharpe|skew|ibs|internal bar|keltner" и др.) - ЕДНА
    # идея (Bullish Harami) беше ОТХВЪРЛЕНА тук защото е концептуално
    # твърде близка до three_inside_up (вече тествана harami-базирана
    # формация в strategies.py, резултат "точно на прага" там - не е
    # смислено да я "преоткриваме" тук); замяна: Rolling Beta spike.
    # ВТОРА кандидат-идея (Elder Ray Bull Power) също беше отхвърлена -
    # ВЕЧЕ Е тук като bullpower_p{p} (семейство #38 от кръг 4).

    # 84) Hull Moving Average (HMA) - WMA-базирана средна, нарочно
    #     конструирана да намали lag СПРЯМО обикновена/експоненциална
    #     средна (2*WMA(n/2) - WMA(n), после пак WMA със sqrt(n)) -
    #     различна "анти-lag" конструкция от SMA/EMA кросоувърите #8/#55 -
    #     цена пресича HMA нагоре - 2 периода = 2.
    for n_hma in (9, 16):
        half_hma = max(int(round(n_hma / 2)), 1)
        sqrt_hma = max(int(round(np.sqrt(n_hma))), 1)
        wma_half = _wma(close, half_hma)
        wma_full = _wma(close, n_hma)
        raw_hma = 2 * wma_half - wma_full
        hma = _wma(raw_hma, sqrt_hma)
        s = (close.shift(1) <= hma.shift(1)) & (close > hma)
        sig[f"hma_n{n_hma}"] = s.fillna(False).to_numpy()

    # 85) Volume Zone Oscillator (VZO) - EMA на обема "подписан" по
    #     посоката на деня (нагоре/надолу), като % от EMA на целия обем -
    #     БАУНДИРАН осцилатор (-100/+100), различен от кумулативните
    #     OBV/PVT/A-D (тях нищо не ги спира да растат неограничено) и от
    #     обемно-претеглените CMF/MFI (различна формула - там тежи
    #     typical-price позиция, не просто знак на деня) - пресичане
    #     над 0 - 2 периода = 2.
    vp_vzo = np.sign(close.diff()).fillna(0) * vol
    for n_vzo in (14, 21):
        vzo = 100 * vp_vzo.ewm(span=n_vzo, adjust=False).mean() / vol.ewm(span=n_vzo, adjust=False).mean()
        s = (vzo.shift(1) <= 0) & (vzo > 0)
        sig[f"vzo_n{n_vzo}"] = s.fillna(False).to_numpy()

    # 86) Keltner Channel ДОЛНА лента отскок - ОГЛЕДАЛНО на Keltner #20
    #     (там е пробив над ГОРНАТА лента - continuation; тук е reversal
    #     отскок от ДОЛНАТА - същата логика "отскок от ниво" като
    #     pivot_s1/s2_bounce #82, но върху ATR-базиран канал, не
    #     floor-trader геометрия) - 2 (период, k) комбинации = 2.
    tr_kc_lb = pd.concat([
        high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    for p_lb, k_lb in ((14, 1.5), (20, 2.0)):
        ema_center_lb = close.ewm(span=p_lb, adjust=False).mean()
        atr_kc_lb = tr_kc_lb.ewm(alpha=1 / p_lb, adjust=False).mean()
        lower_kc = ema_center_lb - k_lb * atr_kc_lb
        s = (low.shift(1) <= lower_kc.shift(1)) & (close > lower_kc) & (close > close.shift(1))
        sig[f"keltnerlower_p{p_lb}_k{k_lb}"] = s.fillna(False).to_numpy()

    # 87) Ulcer Index "нисък риск" режим + пробив - Ulcer Index мери
    #     ДЪЛБОЧИНАТА на drawdown-ите (RMS на % просадка от rolling връх),
    #     различно измерение от ATR/Bollinger (те мерят РАЗМАХ ден-за-ден,
    #     не кумулативна просадка) - комбинация "нисковолатилен ПО
    #     DRAWDOWN режим" + Donchian-стил пробив - 2 прозореца = 2.
    for n_ui in (14, 20):
        roll_max_ui = close.rolling(n_ui).max()
        drawdown_pct_ui = (close - roll_max_ui) / roll_max_ui * 100
        ulcer = np.sqrt((drawdown_pct_ui ** 2).rolling(n_ui).mean())
        low_regime_ui = ulcer <= ulcer.rolling(100).quantile(0.25)
        breakout_ui = close > roll_max_ui.shift(1)
        s = low_regime_ui.shift(1) & breakout_ui
        sig[f"ulcerlowbreak_n{n_ui}"] = s.fillna(False).to_numpy()

    # 88) Gap-up "клъстериране" - БРОЙ gap-up дни в rolling прозорец
    #     достига праг, И днес СЪЩО е gap-up ден - различно ИЗМЕРЕНИЕ от
    #     единичния gap_g_h #6 (там е ЕДНОКРАТНО събитие "днес gap+hold"),
    #     тук е ЧЕСТОТА/клъстериране на повтарящи се gap-up дни във времето
    #     (идея: тикер с чести gap-up дни = по-вероятен "в движение" от
    #     новини) - 2 (прозорец, брой) комбинации = 2.
    gap_cl = open_ / close.shift(1) - 1
    is_gapup_cl = gap_cl >= 0.05
    for w_cl, c_cl in ((10, 3), (20, 4)):
        cluster_count = is_gapup_cl.rolling(w_cl).sum()
        s = is_gapup_cl & (cluster_count >= c_cl)
        sig[f"gapcluster_w{w_cl}_c{c_cl}"] = s.fillna(False).to_numpy()

    # 89) Qstick - rolling средна на (close-open) ПО ТЯЛО (bullish/bearish
    #     "дух" на последните N свещи КАТО СРЕДНА величина, не единична
    #     формация като engulfing/hammer/harami) - пресичане над 0 -
    #     2 периода = 2.
    body_qs = close - open_
    for n_qs in (10, 20):
        qstick = body_qs.rolling(n_qs).mean()
        s = (qstick.shift(1) <= 0) & (qstick > 0)
        sig[f"qstick_n{n_qs}"] = s.fillna(False).to_numpy()

    # 90) "Растящ" Donchian канал - горната лента (high.rolling(w).max())
    #     пробита ДОПЪЛНИТЕЛНО изисква САМАТА ЛЕНТА да се е качвала през
    #     последните 5 дни (каналът "върви нагоре") - различен филтър от
    #     donch_h #1 (обемно потвърждение) и donch_mid #49 (друга точка на
    #     пробив) - тук филтърът е ТРЕНД НА САМИЯ КАНАЛ, не обем/ниво -
    #     2 прозореца = 2.
    for w_dr in (20, 40):
        upper_band_dr = high.rolling(w_dr).max()
        rising_dr = upper_band_dr > upper_band_dr.shift(5)
        breakout_dr = close > upper_band_dr.shift(1)
        s = breakout_dr & rising_dr
        sig[f"donchrising_w{w_dr}"] = s.fillna(False).to_numpy()

    # 91) Rolling skewness на дневната доходност обръща от <=0 към >0 -
    #     СТАТИСТИЧЕСКА форма на разпределението на доходността (трети
    #     момент), различна от z-score mean-reversion #59 (втори момент/
    #     разстояние) - сигнал за повече "дълги десни опашки" (чести
    #     остри нагоре-дни) - 2 прозореца = 2.
    ret_sk = close.pct_change()
    for w_sk in (20, 40):
        skew_sk = ret_sk.rolling(w_sk).skew()
        s = (skew_sk.shift(1) <= 0) & (skew_sk > 0)
        sig[f"retskew_w{w_sk}"] = s.fillna(False).to_numpy()

    # 92) Internal Bar Strength (IBS) екстремум + отскок - (close-low)/
    #     (high-low) на ВЧЕРА близо до 0 (затворил близо до дневния low),
    #     ДНЕС зелен ден - чисто ВЪТРЕШНОДНЕВНА позиция-в-бара метрика,
    #     различна от Stochastic #13 (rolling high/low ПРЕЗ N дни, не
    #     само вчерашния бар) - 2 прага = 2.
    ibs_val = (close - low) / (high - low)
    for t_ibs in (0.15, 0.25):
        s = (ibs_val.shift(1) <= t_ibs) & (close > close.shift(1))
        sig[f"ibs_low_t{t_ibs}"] = s.fillna(False).to_numpy()

    # 93) "Дълбоко" дъно отскок - ОГЛЕДАЛНО на stage2_w100/150 #58 (там е
    #     ДЪЛГО-прозоречен ВРЪХ + тих обем; тук е ДЪЛГО-прозоречно ДЪНО +
    #     reversal, аналогично на lowbounce_w10/20 #36, но на МНОГО по-
    #     дълъг хоризонт - "тикерът е на годишно/полугодишно дъно, но
    #     днес се обръща") - 2 прозореца = 2.
    for w_dl in (100, 150):
        rolled_low_dl = low.rolling(w_dl).min().shift(2)
        made_new_low_dl = close.shift(1) <= rolled_low_dl * 1.03
        s = made_new_low_dl & (close > close.shift(1))
        sig[f"deeplow_bounce_w{w_dl}"] = s.fillna(False).to_numpy()

    # 94) Rolling Beta "скок" спрямо бенчмарк (SPY) - СТАТИСТИЧЕСКА бета
    #     (cov(тикер,бенчмарк)/var(бенчмарк) през rolling прозорец), РАЗЛИЧНА
    #     от relative strength #26 (там е просто разлика в ROC % - АБСОЛЮТНО
    #     представяне, не статистическа чувствителност/наклон спрямо
    #     пазара) - тикер временно се движи МНОГО по-рязко от пазара, И двата
    #     нагоре (положителна бета, не просто волатилност) - 2 прага = 2,
    #     САМО ако е подаден бенчмарк.
    if benchmark_close is not None and not benchmark_close.isna().all():
        bench_beta = benchmark_close.reindex(df.index).ffill()
        stock_ret_beta = close.pct_change()
        bench_ret_beta = bench_beta.pct_change()
        for w_beta, t_beta in ((20, 2.0), (40, 1.75)):
            cov_beta = stock_ret_beta.rolling(w_beta).cov(bench_ret_beta)
            var_beta = bench_ret_beta.rolling(w_beta).var()
            beta_val = cov_beta / var_beta
            s = (beta_val.shift(1) <= t_beta) & (beta_val > t_beta) & (bench_ret_beta > 0) & (stock_ret_beta > 0)
            sig[f"betaspike_w{w_beta}_t{t_beta}"] = s.fillna(False).to_numpy()

    # 95) Rolling "Sharpe-подобно" съотношение (mean(доходност)/std(доходност)
    #     през rolling прозорец) обръща от <=0 към >0 - риск-коригиран
    #     моментум, различен от чист ROC #4 (там е само числителят, без
    #     нормализация по риск/волатилност) - 3 прозореца = 3.
    for w_sh in (10, 20, 30):
        mean_sh = ret_sk.rolling(w_sh).mean()
        std_sh = ret_sk.rolling(w_sh).std()
        sharpe_sh = mean_sh / std_sh
        s = (sharpe_sh.shift(1) <= 0) & (sharpe_sh > 0)
        sig[f"sharpeturn_w{w_sh}"] = s.fillna(False).to_numpy()

    # === КРЪГ 12 (04.11, по молба "продължаваме още стратегии давай") -
    # 10 НОВИ механично различни семейства, 20 нови варианта. Проверени
    # предварително срещу strategies.py каталога - Darvas Box беше НАРОЧНО
    # пропуснат (вече тества там, резултат "леко по-добър от random" -
    # твърде слабо за да го преоткриваме); Aroon кросоувър вече Е тук
    # (семейство #29 от кръг 2).

    # 96) KAMA (Kaufman Adaptive Moving Average) кросоувър - цена пресича
    #     ШЕСТОТО stateful изчисление тук (виж _kama по-горе) - различна
    #     "адаптивност" от McGinley #74 (там скоростта зависи от
    #     СЪОТНОШЕНИЕТО цена/предишна стойност; тук зависи от Efficiency
    #     Ratio - колко "право" се е движила цената) - 2 ER периода = 2.
    for er_p in (10, 20):
        kama_arr = _kama(close.to_numpy(), er_period=er_p)
        kama_s = pd.Series(kama_arr, index=close.index)
        s = (close.shift(1) <= kama_s.shift(1)) & (close > kama_s)
        sig[f"kama_er{er_p}"] = s.fillna(False).to_numpy()

    # 97) Choppiness Index "трендиращ" режим + пробив - ЛОГАРИТМИЧНО
    #     съотношение сума(TR)/диапазон(N дни), различна "trend-quality"
    #     метрика от Ulcer Index #87 (drawdown-базиран) и ADX #14
    #     (directional movement) - комбинирано с Donchian-стил пробив -
    #     2 прозореца = 2.
    tr_chop = pd.concat([
        high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    for n_chop in (14, 20):
        sum_tr_chop = tr_chop.rolling(n_chop).sum()
        range_chop = high.rolling(n_chop).max() - low.rolling(n_chop).min()
        chop = 100 * np.log10(sum_tr_chop / range_chop) / np.log10(n_chop)
        trending_chop = chop <= 38.2
        breakout_chop = close > close.rolling(n_chop).max().shift(1)
        s = trending_chop.shift(1) & breakout_chop
        sig[f"chopbreak_n{n_chop}"] = s.fillna(False).to_numpy()

    # 98) TEMA (Triple EMA) кросоувър - цена пресича 3*EMA1-3*EMA2+EMA3
    #     (нарочно конструирана да намали lag ПОВЕЧЕ от единична EMA,
    #     различна "анти-lag" математика от Hull #84, която е WMA-базирана,
    #     не тройно-EMA-базирана) - 2 периода = 2.
    for n_tema in (10, 20):
        ema1_t = close.ewm(span=n_tema, adjust=False).mean()
        ema2_t = ema1_t.ewm(span=n_tema, adjust=False).mean()
        ema3_t = ema2_t.ewm(span=n_tema, adjust=False).mean()
        tema = 3 * ema1_t - 3 * ema2_t + ema3_t
        s = (close.shift(1) <= tema.shift(1)) & (close > tema)
        sig[f"tema_n{n_tema}"] = s.fillna(False).to_numpy()

    # 99) Klinger Volume Oscillator (ОПРОСТЕН, ЧЕСТНО документирано - не
    #     пълната cm/dm кумулативна-тренд формула на Klinger, а обем
    #     ТЕГЛЕН по дневния РАЗМАХ (high-low) и знак - различно измерение
    #     от OBV #11 (само знак, без размах) и CMF/MFI (тежат ПОЗИЦИЯТА на
    #     затварянето в диапазона, не целия размах)) - EMA бърза-бавна
    #     разлика пресича собствена signal линия - 2 комплекта периоди = 2.
    trend_kvo = np.sign(close.diff()).fillna(1)
    vf_kvo = vol * trend_kvo * (high - low)
    for f_kvo, s_kvo, sig_kvo in ((34, 55, 13), (20, 35, 8)):
        kvo = vf_kvo.ewm(span=f_kvo, adjust=False).mean() - vf_kvo.ewm(span=s_kvo, adjust=False).mean()
        kvo_sig = kvo.ewm(span=sig_kvo, adjust=False).mean()
        s = (kvo.shift(1) <= kvo_sig.shift(1)) & (kvo > kvo_sig)
        sig[f"kvo_f{f_kvo}_s{s_kvo}"] = s.fillna(False).to_numpy()

    # 100) Balance of Power (BOP) изгладен - (close-open)/(high-low),
    #      rolling средно, пресичащо 0 - МАЩАБНО-НЕЗАВИСИМА версия на
    #      Qstick #89 (там е АБСОЛЮТНА разлика close-open в $, тук е
    #      НОРМАЛИЗИРАНА спрямо дневния диапазон - различна "единица") -
    #      2 периода = 2.
    bop_raw = (close - open_) / (high - low)
    for n_bop in (10, 20):
        bop_sm = bop_raw.rolling(n_bop).mean()
        s = (bop_sm.shift(1) <= 0) & (bop_sm > 0)
        sig[f"bop_n{n_bop}"] = s.fillna(False).to_numpy()

    # 101) Camarilla pivot - ФИКСИРАНА геометрична формула от вчерашния
    #      бар, но РАЗЛИЧЕН множител/конструкция от floor-trader pivot
    #      #42 (там R1/R2 от pivot=(H+L+C)/3; тук H3/L3 директно от
    #      prior_close ± 1.1/4*range, без междинен pivot) - пробив над H3
    #      + отскок от L3 = 2.
    range_cam = prior_high_pp - prior_low_pp
    h3_cam = prior_close_pp + range_cam * 1.1 / 4
    l3_cam = prior_close_pp - range_cam * 1.1 / 4
    sig["camarilla_h3_breakout"] = ((prior_close_pp <= h3_cam) & (close > h3_cam)).fillna(False).to_numpy()
    sig["camarilla_l3_bounce"] = ((low.shift(1) <= l3_cam) & (close > l3_cam) & (close > close.shift(1))).fillna(False).to_numpy()

    # 102) "Three Outside Up" - 3-свещна ПОТВЪРДЕНА reversal формация,
    #      основана на ENGULFING (ден2 поглъща тяло на ден1, после ден3
    #      потвърждава с по-високо затваряне) - РАЗЛИЧНА БАЗОВА формация
    #      от three_inside_up в strategies.py (там е HARAMI-базирана - тяло
    #      на ден2 ВЪТРЕ в ден1; тук е ОБРАТНОТО, тяло на ден2 ПОГЛЪЩА ден1)
    #      - 2 варианта (чист + обемно потвърден на ден 2) = 2.
    body_open_2 = open_.shift(1)
    body_close_2 = close.shift(1)
    body_open_1 = open_.shift(2)
    body_close_1 = close.shift(2)
    day1_red = body_close_1 < body_open_1
    day2_green_engulf = (body_close_2 > body_open_2) & (body_open_2 <= body_close_1) & (body_close_2 >= body_open_1)
    day3_confirm = close > body_close_2
    three_outside = day1_red & day2_green_engulf & day3_confirm
    sig["three_outside_up"] = three_outside.fillna(False).to_numpy()
    vol_day2_up = vol.shift(1) > vol.shift(1).rolling(20).mean().shift(1)
    sig["three_outside_up_vconf"] = (three_outside & vol_day2_up).fillna(False).to_numpy()

    # 103) EMA "дъга"/ribbon БИЧИ подредба - НЯКОЛКО EMA строго подредени
    #      (най-бързата > ... > най-бавната), ТОЧНО днес станала вярна -
    #      различна СТРУКТУРА от GMMA кросоувър #72 (там е СРЕДНО от 6
    #      КРАТКИ срещу СРЕДНО от 6 ДЪЛГИ, 2 групи; тук е СТРОГА подредба
    #      на ВСЯКА отделна EMA една спрямо друга, N средни наведнъж) -
    #      2 комплекта = 2.
    def _ribbon_aligned(periods):
        emas = [close.ewm(span=p, adjust=False).mean() for p in periods]
        aligned_today = emas[0] > emas[1]
        for a, b in zip(emas[1:], emas[2:]):
            aligned_today = aligned_today & (a > b)
        aligned_yesterday = emas[0].shift(1) > emas[1].shift(1)
        for a, b in zip(emas[1:], emas[2:]):
            aligned_yesterday = aligned_yesterday & (a.shift(1) > b.shift(1))
        return aligned_today & ~aligned_yesterday.fillna(False)

    sig["ribbon_slow_5"] = _ribbon_aligned((5, 10, 15, 20, 25)).fillna(False).to_numpy()
    sig["ribbon_fast_4"] = _ribbon_aligned((3, 6, 9, 12)).fillna(False).to_numpy()

    # 104) Weighted Close (H+L+2C)/4 пресича собствената си rolling средна
    #      - СЪЩАТА MA-кросоувър МЕХАНИКА като macross #8, но различен
    #      ВХОДЕН сигнал (теглена типична цена с ДВОЕН акцент на
    #      затварянето, не чист close) - 2 периода = 2.
    wc = (high + low + 2 * close) / 4
    for n_wc in (10, 20):
        wc_ma = wc.rolling(n_wc).mean()
        s = (wc.shift(1) <= wc_ma.shift(1)) & (wc > wc_ma)
        sig[f"wclose_n{n_wc}"] = s.fillna(False).to_numpy()

    # 105) MA "ускорение" (КОНВЕКСНОСТ) обръща положително - СРАВНЯВА
    #      5-дневния ROC НА САМАТА пълзяща средна СЕГА срещу преди 5 дни -
    #      различно от linear-regression slope обрат #46 (там е ЕДНА OLS
    #      права през прозореца = средна СКОРОСТ; тук е ПРОМЯНА в скоростта
    #      = УСКОРЕНИЕ, втора производна) - 2 прозореца = 2.
    for w_ac in (10, 20):
        ma_ac = close.rolling(w_ac).mean()
        roc_ma_ac = ma_ac.diff(5)
        accel = roc_ma_ac - roc_ma_ac.shift(5)
        s = (accel.shift(1) <= 0) & (accel > 0)
        sig[f"maaccel_w{w_ac}"] = s.fillna(False).to_numpy()

    # === КРЪГ 13 (04.11, по молба "още") - 9 НОВИ механично различни
    # семейства, 18 нови варианта. Проверени предварително срещу
    # strategies.py каталога - Pocket Pivot беше НАРОЧНО пропуснат (вече
    # тестван там, смесен извън-извадков резултат); RSI "failure swing"
    # беше ОТХВЪРЛЕН на етап планиране - концептуално твърде близък до
    # вече тествания rsi_bulldiv #46 (и двата са "RSI прави по-високо
    # дъно докато цената прави по-ниско" формации); замяна: Donchian
    # канал ПОЗИЦИЯ-процентил.

    # 106) VPCI (Volume Price Confirmation Indicator, ОПРОСТЕНО, честно
    #      документирано - Buff Dormeier оригиналът ползва ДВА различни
    #      прозореца едновременно, тук е ЕДИН за простота) - сравнява
    #      обемно-претеглената средна цена (VWMA) СРЕЩУ обикновената SMA,
    #      умножено по текущия обемен "мултипликатор" - различна комбинация
    #      от VWAP reclaim #24 (там е просто пресичане, не произведение от
    #      3 компонента) - пресичане над 0 - 2 прозореца = 2.
    for n_vpci in (20, 10):
        vwma_vpci = (close * vol).rolling(n_vpci).sum() / vol.rolling(n_vpci).sum()
        sma_vpci = close.rolling(n_vpci).mean()
        vpc = vwma_vpci - sma_vpci
        vpr = vwma_vpci / sma_vpci
        vm_vpci = vol / vol.rolling(n_vpci).mean()
        vpci = vpc * vpr * vm_vpci
        s = (vpci.shift(1) <= 0) & (vpci > 0)
        sig[f"vpci_n{n_vpci}"] = s.fillna(False).to_numpy()

    # 107) Chaikin Volatility "разширение" - EMA на дневния размах (H-L)
    #      СРАВНЕНА СРЕЩУ СЕБЕ СИ преди N дни (% промяна В РАЗШИРЕНИЕТО,
    #      не абсолютно ниво) - различно от ATR разширение #33 (там е
    #      АБСОЛЮТНО ниво на ATR спрямо своя праг, не темп на промяна) -
    #      2 периода = 2.
    for n_cv in (10, 14):
        ema_range_cv = (high - low).ewm(span=n_cv, adjust=False).mean()
        chaikin_vol = (ema_range_cv - ema_range_cv.shift(n_cv)) / ema_range_cv.shift(n_cv) * 100
        s = (chaikin_vol.shift(1) <= 0) & (chaikin_vol > 0) & (close > close.shift(1))
        sig[f"chaikinvol_n{n_cv}"] = s.fillna(False).to_numpy()

    # 108) PVI (Positive Volume Index) нов връх - ОГЛЕДАЛНО на NVI #85
    #      (там кумулативният индекс се обновява САМО в дни с ПО-НИСЪК
    #      обем от вчера; тук - САМО в дни с ПО-ВИСОК обем, обратна
    #      логика) - 2 прозореца = 2.
    ret_pct_pvi = close.pct_change()
    pvi = 1000.0 * (1.0 + ret_pct_pvi.where(vol > vol.shift(1), 0.0).fillna(0.0)).cumprod()
    for w_pvi in (20, 40):
        pvi_roll_max = pvi.rolling(w_pvi).max().shift(1)
        s = pvi > pvi_roll_max
        sig[f"pvi_newhigh_w{w_pvi}"] = s.fillna(False).to_numpy()

    # 109) Donchian канал ПОЗИЦИЯ-процентил - (close-мин)/(макс-мин) В
    #      РАМКИТЕ на N-дневния Donchian канал пресича праг нагоре -
    #      НЕПРЕКЪСНАТА метрика, аналог на Bollinger %B #62, но за
    #      Donchian геометрия (min/max), не Bollinger (SMA+std) - различно
    #      и от donch_mid #49 (там е ФИКСИРАНА среда 50%, тук е configурируем
    #      праг) и donchrising #90 (там е ТРЕНД на лентата, не позиция в
    #      нея) - 2 прозореца = 2.
    for w_dp in (20, 40):
        roll_max_dp = high.rolling(w_dp).max()
        roll_min_dp = low.rolling(w_dp).min()
        pos_pct_dp = (close - roll_min_dp) / (roll_max_dp - roll_min_dp)
        s = (pos_pct_dp.shift(1) <= 0.9) & (pos_pct_dp > 0.9)
        sig[f"donchpos_w{w_dp}"] = s.fillna(False).to_numpy()

    # 110) "Outside day" reversal - ЕДИНИЧЕН бар, чийто диапазон ИЗЦЯЛО
    #      поглъща вчерашния (high>вчерашния high И low<вчерашния low),
    #      затварящ нагоре - РАЗЛИЧНА структура от three_outside_up #102
    #      (там е 3-дневна ТЯЛО-базирана engulfing формация; тук е
    #      ЕДИНИЧЕН ден, ЦЯЛ диапазон включително фитили, не само тяло) -
    #      2 варианта (чист + обемно потвърден) = 2.
    outside_day = (high > high.shift(1)) & (low < low.shift(1))
    bullish_outside = outside_day & (close > open_) & (close > close.shift(1))
    sig["outsideday"] = bullish_outside.fillna(False).to_numpy()
    vol_above_avg_od = vol > vol.rolling(20).mean()
    sig["outsideday_vconf"] = (bullish_outside & vol_above_avg_od).fillna(False).to_numpy()

    # 111) Random Walk Index (RWI) High - сравнява РЕАЛНОТО движение
    #      high[i]-low[i-n] СРЕЩУ очакваното движение на ЧИСТ случаен
    #      разходка (ATR*sqrt(n)) - ЕДИНСТВЕНОТО тук семейство, което
    #      тества "доколко ценовото движение е статистически НЕслучайно",
    #      различно от z-score #52 (там е разстояние от средната, не
    #      сравнение с random-walk очакване) - 2 периода = 2.
    tr_rwi = pd.concat([
        high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    for n_rwi in (7, 14):
        atr_rwi = tr_rwi.ewm(alpha=1 / n_rwi, adjust=False).mean()
        rwi_high = (high - low.shift(n_rwi)) / (atr_rwi * np.sqrt(n_rwi))
        s = (rwi_high.shift(1) <= 1.0) & (rwi_high > 1.0)
        sig[f"rwihigh_n{n_rwi}"] = s.fillna(False).to_numpy()

    # 112) Schaff Trend Cycle (ОПРОСТЕНО, честно документирано - оригиналът
    #      прилага Stochastic ДВУКРАТНО/цикъл върху MACD; тук е ЕДНОКРАТНО
    #      приложение + единична EMA изглаждане за простота) - Stochastic
    #      формулата, приложена към MACD линията - различна ЦЕЛ от
    #      Stochastic RSI #67 (там е приложена към RSI, не MACD) - 2
    #      цикъла = 2.
    ema_f_stc = close.ewm(span=12, adjust=False).mean()
    ema_s_stc = close.ewm(span=26, adjust=False).mean()
    macd_stc = ema_f_stc - ema_s_stc
    for n_stc in (10, 23):
        macd_min_stc = macd_stc.rolling(n_stc).min()
        macd_max_stc = macd_stc.rolling(n_stc).max()
        stoch_macd = (macd_stc - macd_min_stc) / (macd_max_stc - macd_min_stc) * 100
        stc = stoch_macd.ewm(span=3, adjust=False).mean()
        s = (stc.shift(1) <= 25) & (stc > 25)
        sig[f"stc_n{n_stc}"] = s.fillna(False).to_numpy()

    # 113) KST (Know Sure Thing, Pring) - ВЗВЕШЕНА сума от 4 изгладени ROC
    #      периода (тегла 1-2-3-4, по-дългите периоди тежат повече) -
    #      различна "агрегация" от Coppock #60 (там са само 2 ROC-а, равно
    #      тежени, WMA-изгладени) - пресичане на signal линия - 2 комплекта
    #      периоди (стандартен + компресиран) = 2.
    def _kst(roc_periods, sma_periods, sig_period):
        total = pd.Series(0.0, index=close.index)
        weight = 1
        for rp, sp in zip(roc_periods, sma_periods):
            roc_k = close.pct_change(rp) * 100
            rcma_k = roc_k.rolling(sp).mean()
            total = total + rcma_k * weight
            weight += 1
        kst_signal = total.rolling(sig_period).mean()
        return total, kst_signal

    kst_std, kst_std_sig = _kst((10, 15, 20, 30), (10, 10, 10, 15), 9)
    sig["kst_std"] = ((kst_std.shift(1) <= kst_std_sig.shift(1)) & (kst_std > kst_std_sig)).fillna(False).to_numpy()
    kst_fast, kst_fast_sig = _kst((5, 8, 10, 15), (5, 5, 5, 8), 5)
    sig["kst_fast"] = ((kst_fast.shift(1) <= kst_fast_sig.shift(1)) & (kst_fast > kst_fast_sig)).fillna(False).to_numpy()

    # 114) Регресионен канал ДОЛНА лента отскок - ОГЛЕДАЛНО на regchannel
    #      #54 (там е пробив над ГОРНАТА лента, continuation; тук е
    #      reversal отскок от ДОЛНАТА, k=-2.0 вместо +2.0 в СЪЩАТА
    #      _regression_channel_upper функция) - 2 прозореца = 2.
    for w_rcl in (20, 40):
        lower_channel = _regression_channel_upper(close, w_rcl, -2.0)
        s = (low.shift(1) <= lower_channel.shift(1)) & (close > lower_channel) & (close > close.shift(1))
        sig[f"regchannel_lower_w{w_rcl}"] = s.fillna(False).to_numpy()

    return sig


def _forward_return(close: np.ndarray, open_: np.ndarray, exit_name: str) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    if exit_name == "next_open":
        out[: n - 1] = (open_[1:] - close[: n - 1]) / close[: n - 1] * 100
        return out
    h = int(exit_name.split("_")[1][:-1])
    if n > h:
        out[: n - h] = (close[h:] - close[: n - h]) / close[: n - h] * 100
    return out


def _forward_max_high(high: np.ndarray, h: int) -> np.ndarray:
    """result[i] = max(high[i+1 : i+1+h]) - истински vector операция чрез
    sliding_window_view (виж честната бележка за maxrunup в
    strategy_backtest.py - по-честен тест на "хванахме ли скока", не само
    затварянето на хоризонта)."""
    n = len(high)
    out = np.full(n, np.nan)
    if n > h:
        windows = sliding_window_view(high[1:], h)
        m = windows.max(axis=1)
        out[: len(m)] = m
    return out


def _simulate_target_stop_return(low: np.ndarray, high: np.ndarray, close: np.ndarray, i: int, price_today: float, h: int, target_pct: float, stop_pct: float) -> float:
    """КРЪГ 2 (03.11, по изрична молба "искам да излизам на 10% печалба и
    повече"): реалистична take-profit/stop-loss симулация, ден по ден -
    държиш от close(i) до ПЪРВОТО от: (1) low докосва -stop_pct% -> излизаш
    на загуба (ПРОВЕРЕНО ПЪРВО - консервативно, същата философия като
    _simulate_stopped_return в strategy_backtest.py: ако двете се случат в
    СЪЩИЯ ден, не можем да знаем реда по дневни свещи, затова приемаме
    по-лошия случай); (2) high докосва +target_pct% -> излизаш на печалба
    (limit sell точно на целта); (3) никое от двете до край на хоризонта ->
    излизаш на close(i+h), каквото излезе."""
    stop_price = price_today * (1 - stop_pct / 100)
    target_price = price_today * (1 + target_pct / 100)
    for j in range(i + 1, i + h + 1):
        if low[j] <= stop_price:
            return round(-stop_pct, 2)
        if high[j] >= target_price:
            return round(target_pct, 2)
    return round((close[i + h] - price_today) / price_today * 100, 2)


def _new_bucket():
    """ВАЖНО: EXITS и RUNUP_HORIZON се ПРЕСИЧАТ (close_1d/3d/5d/10d са и в
    двата) - ако построим речника с двойно **unpacking, ключовете от
    RUNUP_HORIZON ПРЕЗАПИСВАТ тези от EXITS и 'ret' списъкът изчезва.
    Затова строим bucket[e] постепенно, добавяйки 'ret', 'runup' и
    'target_sim' (кръг 2) в ЕДИН И СЪЩ под-речник, когато е и двете."""
    bucket = {"signals": 0, "symbols": set()}
    for e in EXITS:
        bucket[e] = {"ret": []}
    for e in RUNUP_HORIZON:
        sub = bucket.setdefault(e, {})
        sub["runup"] = []
        sub["target_sim"] = []
    return bucket


def process_symbol(
    symbol: str, df: pd.DataFrame, singles_acc: dict, combos_acc: dict, make_combos: bool,
    target_pct: float = DEFAULT_TARGET_PCT, stop_pct: float = DEFAULT_STOP_PCT,
    benchmark_close: pd.Series = None,
) -> int:
    n = len(df)
    max_lookahead = MAX_HORIZON_DAYS
    if n < MIN_BARS + max_lookahead + 1:
        return 0

    sig_lib = build_signal_library(df, benchmark_close=benchmark_close)
    close_arr = df["close"].to_numpy()
    open_arr = df["open"].to_numpy()
    high_arr = df["high"].to_numpy()
    low_arr = df["low"].to_numpy()

    fwd_ret = {e: _forward_return(close_arr, open_arr, e) for e in EXITS}
    # ВАЖНО (поправка намерена при тестване на кръг 2): _forward_max_high
    # връща СУРОВАТА max high ЦЕНА, не % доходност - директно сравнение
    # с 10/20 (прагове в %) би било грешно (почти винаги False, защото
    # цените на penny stocks рядко надвишават 10-20 в АБСОЛЮТНА стойност).
    # Преобразуваме във % спрямо входната цена ВЕДНАГА тук, вектор ризирано
    # за целия тикер наведнъж - виж maxrunup_by_horizon в strategy_backtest.py
    # за същата формула, (best_high - price_today) / price_today * 100.
    fwd_runup = {
        e: (_forward_max_high(high_arr, h) - close_arr) / close_arr * 100
        for e, h in RUNUP_HORIZON.items()
    }

    price_ok = (close_arr > 0) & (close_arr <= config.MAX_UNIVERSE_PRICE) & (close_arr >= SUBNICKEL_PRICE_FLOOR)

    n_signals_recorded = 0
    last_valid_idx = n - 1 - max_lookahead
    for i in range(MIN_BARS, last_valid_idx + 1):
        if not price_ok[i]:
            continue

        fired = sorted(name for name, arr in sig_lib.items() if arr[i])
        is_random_day = (i - MIN_BARS) % RANDOM_BASELINE_EVERY_NTH_DAY == 0
        names_to_record = list(fired)
        if is_random_day:
            names_to_record.append("random_baseline")
        if not names_to_record:
            continue

        price_today = close_arr[i]
        # КРЪГ 2: смятаме target/stop симулацията ВЕДНЪЖ на ден (не на
        # всяко име, което е гръмнало) - леко O(h) на валиден ден, не на
        # всеки ден от историята (виж бележката в _simulate_target_stop_return).
        target_sim_today = {
            e: _simulate_target_stop_return(low_arr, high_arr, close_arr, i, price_today, h, target_pct, stop_pct)
            for e, h in RUNUP_HORIZON.items()
        }

        for name in names_to_record:
            bucket = singles_acc.setdefault(name, _new_bucket())
            bucket["signals"] += 1
            bucket["symbols"].add(symbol)
            for e in EXITS:
                bucket[e]["ret"].append(fwd_ret[e][i])
            for e in RUNUP_HORIZON:
                bucket[e]["runup"].append(fwd_runup[e][i])
                bucket[e]["target_sim"].append(target_sim_today[e])
            n_signals_recorded += 1

        if make_combos and len(fired) >= 2:
            for a, b in itertools.combinations(fired, 2):
                combo_name = f"{a}+{b}"
                bucket = combos_acc.setdefault(combo_name, _new_bucket())
                bucket["signals"] += 1
                bucket["symbols"].add(symbol)
                for e in EXITS:
                    bucket[e]["ret"].append(fwd_ret[e][i])
                for e in RUNUP_HORIZON:
                    bucket[e]["runup"].append(fwd_runup[e][i])
                    bucket[e]["target_sim"].append(target_sim_today[e])

    return n_signals_recorded


def summarize_acc(acc: dict, min_signals: int, min_symbols: int, name_col: str, target_pct: float = DEFAULT_TARGET_PCT, stop_pct: float = DEFAULT_STOP_PCT) -> pd.DataFrame:
    target_label = f"{target_pct:g}pct"
    rows = []
    for name, bucket in acc.items():
        if bucket["signals"] < min_signals or len(bucket["symbols"]) < min_symbols:
            continue
        row = {name_col: name, "signals": bucket["signals"], "symbols_used": len(bucket["symbols"])}
        for e in EXITS:
            vals = pd.Series(bucket[e]["ret"]).dropna()
            if vals.empty:
                continue
            row[f"win_rate_{e}_%"] = round((vals > 0).mean() * 100, 1)
            row[f"avg_ret_{e}_%"] = round(vals.mean(), 2)
            row[f"median_ret_{e}_%"] = round(vals.median(), 2)
            row[f"max_loss_{e}_%"] = round(vals.min(), 2)
        for e in RUNUP_HORIZON:
            runup_vals = pd.Series(bucket[e]["runup"]).dropna()
            if not runup_vals.empty:
                row[f"caught_10pct_spike_{e}_%"] = round((runup_vals >= 10).mean() * 100, 1)
                row[f"caught_20pct_spike_{e}_%"] = round((runup_vals >= 20).mean() * 100, 1)
            # КРЪГ 2: реалистична take-profit/stop симулация - виж
            # _simulate_target_stop_return. hit_target_Xpct_% = % от
            # сигналите, при които РЕАЛНО си излязъл на +target_pct% или
            # повече (не просто "доближил се е") - точният отговор на
            # "колко често намирам penny stock, от който излизам на X%+".
            sim_vals = pd.Series(bucket[e]["target_sim"]).dropna()
            if not sim_vals.empty:
                row[f"hit_target_{target_label}_{e}_%"] = round((sim_vals >= target_pct - 0.01).mean() * 100, 1)
                row[f"stopped_out_{e}_%"] = round((sim_vals <= -stop_pct + 0.01).mean() * 100, 1)
                row[f"avg_ret_targetsim_{e}_%"] = round(sim_vals.mean(), 2)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=250, help="Колко календарни дни история назад (yfinance период).")
    parser.add_argument("--offset-days", type=int, default=0, help="Извън-извадков прозорец - виж горния docstring (същият протокол като strategy_backtest.py).")
    parser.add_argument("--symbols", nargs="*", default=None, help="Ръчен списък тикери вместо автоматичния universe.")
    parser.add_argument("--no-live-universe", action="store_true", help="Пропусни живия universe.get_universe(), ползвай само статичния списък.")
    parser.add_argument("--no-combos", action="store_true", help="Само 209 единични варианта (без двойки) - много по-бързо.")
    parser.add_argument("--min-signals", type=int, default=DEFAULT_MIN_SIGNALS, help="Минимален брой сигнали преди да се докладва стратегия/комбинация.")
    parser.add_argument("--min-symbols", type=int, default=DEFAULT_MIN_SYMBOLS, help="Минимален брой РАЗЛИЧНИ тикери, допринесли сигнали.")
    parser.add_argument("--main-exit", default="close_5d", choices=EXITS, help="ЕДИН предварително избран хоризонт за класирането на топ 10 (виж честна бележка #1 - не позволяваме избор на 'най-добрия' изход след факта).")
    parser.add_argument("--top", type=int, default=10, help="Колко стратегии/комбинации да покаже в класацията.")
    parser.add_argument("--target-pct", type=float, default=DEFAULT_TARGET_PCT, help="Целева печалба %% за take-profit симулацията (по подразбиране 10 - 'излизам на 10%% печалба и повече').")
    parser.add_argument("--stop-pct", type=float, default=DEFAULT_STOP_PCT, help="Stop-loss %% за take-profit симулацията (по подразбиране 15).")
    parser.add_argument(
        "--rank-by", default="target_hit", choices=["target_hit", "win_rate"],
        help=(
            "'target_hit' (по подразбиране, кръг 2): класирай по hit_target_Xpct_{main-exit}_%% - колко често "
            "РЕАЛНО излизаш на --target-pct%% или повече (take-profit/stop симулация). "
            "'win_rate': старото класиране по win_rate_{main-exit}_%% (просто положителна/отрицателна доходност)."
        ),
    )
    parser.add_argument("--benchmark", default="SPY", help="Пазарен бенчмарк за relative-strength семейството (кръг 3) - празен низ ('') пропуска семейството изцяло.")
    args = parser.parse_args()

    total_days = args.days + args.offset_days
    symbols = args.symbols or _get_universe_symbols(include_live=not args.no_live_universe)
    log.info(
        "Масово търсене: %d тикера, %d дни назад (%s), 382 единични варианта%s, изходи %s, цел +%.1f%%/stop -%.1f%%.",
        len(symbols), args.days,
        "извън-извадков прозорец, offset=%d дни" % args.offset_days if args.offset_days else "скорошен прозорец",
        " + до ~72771 двойки" if not args.no_combos else " (без комбинации)",
        EXITS, args.target_pct, args.stop_pct,
    )

    benchmark_df = pd.DataFrame()
    if args.benchmark:
        benchmark_df = load_history(args.benchmark, total_days)
        if args.offset_days and not benchmark_df.empty:
            benchmark_df = benchmark_df.iloc[: -args.offset_days] if len(benchmark_df) > args.offset_days else benchmark_df.iloc[0:0]
        if benchmark_df.empty:
            log.warning("Бенчмарк %s: няма данни - relative-strength семейството (кръг 3) ще е изключено (ще връща False навсякъде).", args.benchmark)
        else:
            log.info("Бенчмарк %s: %d бара история.", args.benchmark, len(benchmark_df))

    singles_acc, combos_acc = {}, {}
    total_recorded = 0
    for idx, symbol in enumerate(symbols, 1):
        df = load_history(symbol, total_days)
        if args.offset_days:
            df = df.iloc[: -args.offset_days] if len(df) > args.offset_days else df.iloc[0:0]
        if df.empty:
            log.warning("[%d/%d] %s: няма данни, пропускам.", idx, len(symbols), symbol)
            continue
        bench_close = benchmark_df["close"] if not benchmark_df.empty else None
        n_rec = process_symbol(symbol, df, singles_acc, combos_acc, make_combos=not args.no_combos, target_pct=args.target_pct, stop_pct=args.stop_pct, benchmark_close=bench_close)
        total_recorded += n_rec
        log.info("[%d/%d] %s: %d бара история, %d сигнални записа.", idx, len(symbols), symbol, len(df), n_rec)

    if total_recorded == 0:
        log.info("Няма нито един сигнал в целия тестван период/universe.")
        return

    singles_df = summarize_acc(singles_acc, args.min_signals, args.min_symbols, "strategy", args.target_pct, args.stop_pct)
    combos_df = summarize_acc(combos_acc, args.min_signals, args.min_symbols, "combo", args.target_pct, args.stop_pct) if not args.no_combos else pd.DataFrame()

    singles_df.to_csv("mass_search_singles_summary.csv", index=False)
    if not combos_df.empty:
        combos_df.to_csv("mass_search_combos_summary.csv", index=False)

    target_label = f"{args.target_pct:g}pct"
    if args.rank_by == "target_hit":
        main_win_col = f"hit_target_{target_label}_{args.main_exit}_%"
    else:
        main_win_col = f"win_rate_{args.main_exit}_%"
    main_avg_col = f"avg_ret_{args.main_exit}_%" if args.rank_by == "win_rate" else f"avg_ret_targetsim_{args.main_exit}_%"

    baseline_rows = singles_df[singles_df["strategy"] == "random_baseline"]
    baseline_win = float(baseline_rows[main_win_col].iloc[0]) if not baseline_rows.empty and main_win_col in baseline_rows.columns else None
    if baseline_win is None:
        log.warning("random_baseline няма достатъчно сигнали за сравнение (виж --min-signals) - топ 10 по-долу е БЕЗ сравнение с контролна група, по-слабо доказателство.")

    real_singles = singles_df[singles_df["strategy"] != "random_baseline"].copy()
    real_singles["type"] = "single"
    real_singles = real_singles.rename(columns={"strategy": "name"})
    if not combos_df.empty:
        combos_df2 = combos_df.rename(columns={"combo": "name"})
        combos_df2["type"] = "combo"
        all_candidates = pd.concat([real_singles, combos_df2], ignore_index=True, sort=False)
    else:
        all_candidates = real_singles

    if main_win_col not in all_candidates.columns:
        log.info("Нито една стратегия/комбинация няма достатъчно сигнали на хоризонт %s при --min-signals %d / --min-symbols %d.", args.main_exit, args.min_signals, args.min_symbols)
        return

    all_candidates = all_candidates.dropna(subset=[main_win_col])
    if baseline_win is not None:
        all_candidates["edge_vs_baseline_%"] = (all_candidates[main_win_col] - baseline_win).round(1)
        sort_cols, sort_asc = ["edge_vs_baseline_%", "signals"], [False, False]
    else:
        sort_cols, sort_asc = [main_avg_col, "signals"], [False, False]

    top = all_candidates.sort_values(by=sort_cols, ascending=sort_asc).head(args.top)
    top.to_csv("mass_search_top10.csv", index=False)

    metric_label = f"hit_target_{target_label}" if args.rank_by == "target_hit" else "win_rate"
    log.info(
        "\n=== random_baseline (контрола, хоризонт %s, метрика %s) === %s=%s%% (сравни топ 10 срещу това)",
        args.main_exit, metric_label, metric_label, baseline_win if baseline_win is not None else "н/д",
    )
    log.info(
        "\n=== ТОП %d ПО %s (класирано по хоризонт %s, --rank-by %s, >= %d сигнала / >= %d тикера) ===\n%s",
        args.top, "edge_vs_baseline_%" if baseline_win is not None else main_avg_col, args.main_exit, args.rank_by,
        args.min_signals, args.min_symbols, top.to_string(index=False),
    )
    log.info(
        "\nРезюме единични: mass_search_singles_summary.csv (%d реда) | "
        "Резюме комбинации: mass_search_combos_summary.csv (%d реда) | "
        "Топ %d: mass_search_top10.csv\n"
        "ЧЕСТНО: прочети честните ограничения в началото на този файл. С над 89 000 "
        "тествани стратегия×изход комбинации, НЯКОЛКО горни резултата ТРЯБВА да изглеждат "
        "добри чисто случайно (multiple-testing). Преди да вярваш на топ %d: пусни СЪЩАТА "
        "команда с '--offset-days 250', после с '--offset-days 500', и сравни - истинска "
        "находка остава стабилна (сходен %s, бие random_baseline) в ВСИЧКИ 3 "
        "прозорца, не само в този.",
        len(singles_df), len(combos_df), args.top, args.top, metric_label,
    )


if __name__ == "__main__":
    main()

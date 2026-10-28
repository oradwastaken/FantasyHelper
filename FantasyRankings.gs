  function onOpen() {
    SpreadsheetApp.getUi()
      .createMenu('Fantasy Helper')
      .addItem(
        'Calculate undrafted player rankings',
        'rankAllUndraftedPlayers'
      )
      .addItem(
        'Calculate all player rankings',
        'rankAllPlayers'
      )
      .addItem(
        'Calculate H2H pickup values',
        'calculateH2HPickupValues'
      )
      .addItem(
        'Find Trades',
        'findTrades'
      )
      .addItem(
        'Stop calculating player rankings',
        'stopRankingCalculations'
      )
      .addToUi();
  }

  function stopRankingCalculations() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const resultsSheet = ss.getSheetByName('Simulated Rankings');

    PropertiesService
      .getScriptProperties()
      .setProperty('STOP_RANKINGS', 'true');

    if (resultsSheet) {
      resultsSheet.getRange('G1').setValue(true);
      resultsSheet.getRange('G2').setValue('Stop requested…');
    }
  }


    function onEdit(e) {
    if (!e || !e.range) return;

    const range = e.range;

    if (
      range.getSheet().getName() === 'Roster Comparison' &&
      range.getA1Notation() === 'G1' &&
      e.value === 'TRUE'
    ) {
      PropertiesService
        .getScriptProperties()
        .setProperty('STOP_RANKINGS', 'true');
    }
  }

  function rankAllUndraftedPlayers() {
    rankPlayers(false);
  }

  function rankAllPlayers() {
    rankPlayers(true);
  }

  function rankPlayers(includeAllPlayers) {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const players = ss.getSheetByName('Player Values - Cats');
    const comparison = ss.getSheetByName('Roster Comparison');
    const resultsSheet = ss.getSheetByName('Simulated Rankings');

    const normalize = value =>
      String(value ?? '').trim();

    const firstDataRow = 3;
    const numSourceRows =
      players.getLastRow() - firstDataRow + 1;

    const stopCell = resultsSheet.getRange('G1');
    const properties =
      PropertiesService.getScriptProperties();

    const teams = comparison
      .getRange('A5:A12')
      .getValues()
      .flat()
      .map(normalize)
      .filter(Boolean);

    const targetTeam = 'Rob/Orad';
    const targetTeamIndex = teams.indexOf(targetTeam);

    if (targetTeamIndex === -1) {
      throw new Error(
        'Rob/Orad was not found in Roster Comparison!A5:A12.'
      );
    }

    const teamIndex = new Map();

    teams.forEach((team, index) => {
      teamIndex.set(team, index);
    });

    // D:AB includes status, name, and category data.
    const sourceData = players
      .getRange(firstDataRow, 4, numSourceRows, 25)
      .getValues();

    const playerNames = sourceData.map(row =>
      normalize(row[1])
    );

    const playerStatuses = sourceData.map(row =>
      normalize(row[0])
    );

    const categoryStartIndex = 11; // O within D:AB
    const categoryCount = 14;

    const sums = teams.map(() =>
      Array(categoryCount).fill(0)
    );

    const counts = teams.map(() =>
      Array(categoryCount).fill(0)
    );

    const sourceByName = new Map();

    for (let i = 0; i < sourceData.length; i++) {
      const name = playerNames[i];
      const status = playerStatuses[i];

      if (name !== '') {
        sourceByName.set(name, {
          sourceIndex: i,
          status: status
        });
      }

      if (!teamIndex.has(status)) {
        continue;
      }

      const teamNumber = teamIndex.get(status);

      for (
        let category = 0;
        category < categoryCount;
        category++
      ) {
        const value =
          sourceData[i][categoryStartIndex + category];

        if (
          typeof value === 'number' &&
          Number.isFinite(value)
        ) {
          sums[teamNumber][category] += value;
          counts[teamNumber][category]++;
        }
      }
    }

    // Preserve currently listed players that belong in this run.
    const existingValues = resultsSheet
      .getRange(
        2,
        1,
        resultsSheet.getMaxRows() - 1,
        3
      )
      .getValues();

    let oldDataLastRow = 1;
    const outputNames = [];
    const seenNames = new Set();

    for (let i = 0; i < existingValues.length; i++) {
      const name = normalize(existingValues[i][0]);

      if (
        existingValues[i].some(value => value !== '')
      ) {
        oldDataLastRow = i + 2;
      }

      if (
        name !== '' &&
        !seenNames.has(name) &&
        sourceByName.has(name) &&
        (includeAllPlayers ||
          sourceByName.get(name).status === 'Undrafted')
      ) {
        outputNames.push(name);
        seenNames.add(name);
      }
    }

    // Add players not already present in the output.
    for (let i = 0; i < playerNames.length; i++) {
      const name = playerNames[i];

      if (
        name !== '' &&
        (includeAllPlayers ||
          playerStatuses[i] === 'Undrafted') &&
        !seenNames.has(name)
      ) {
        outputNames.push(name);
        seenNames.add(name);
      }
    }

    const outputRowByName = new Map();

    outputNames.forEach((name, index) => {
      outputRowByName.set(name, index);
    });

    properties.deleteProperty('STOP_RANKINGS');

    stopCell.setValue(false);
    resultsSheet.getRange('H1').setValue('Stop script!');
    resultsSheet.getRange('E1').setValue('Progress');
    resultsSheet.getRange('E2').setValue('Calculating…');

    if (oldDataLastRow >= 2) {
      resultsSheet
        .getRange(2, 3, oldDataLastRow - 1, 1)
        .setValues(
          Array(oldDataLastRow - 1).fill(['Outdated'])
        );
    }

    const candidateIndexes = [];

    for (let i = 0; i < sourceData.length; i++) {
      if (
        playerNames[i] !== '' &&
        (includeAllPlayers || playerStatuses[i] === 'Undrafted')
      ) {
        candidateIndexes.push(i);
      }
    }

    const stagedValues = candidateIndexes.map(index => [
      playerNames[index],
      ''
    ]);

    const rankByName = new Map();

    let completed = 0;
    const total = candidateIndexes.length;

    for (
      let candidateNumber = 0;
      candidateNumber < candidateIndexes.length;
      candidateNumber++
    ) {
      const stopRequested =
        stopCell.getValue() === true ||
        properties.getProperty('STOP_RANKINGS') === 'true';

      if (stopRequested) {
        resultsSheet.getRange('E2').setValue(
          `Stopped: ${completed} of ${total} complete`
        );
        break;
      }

      const sourceIndex =
        candidateIndexes[candidateNumber];

      const candidateName =
        playerNames[sourceIndex];

      const candidateRow =
        sourceData[sourceIndex];

      const removeFromTargetTeam =
        includeAllPlayers &&
        playerStatuses[sourceIndex] === targetTeam;

      const simulatedAverages = [];

      for (
        let category = 0;
        category < categoryCount;
        category++
      ) {
        let sum = sums[targetTeamIndex][category];
        let count = counts[targetTeamIndex][category];

        const candidateValue =
          candidateRow[categoryStartIndex + category];

        if (
          typeof candidateValue === 'number' &&
          Number.isFinite(candidateValue)
        ) {
          if (removeFromTargetTeam) {
            sum -= candidateValue;
            count--;
          } else {
            sum += candidateValue;
            count++;
          }
        }

        simulatedAverages.push(
          count > 0 ? sum / count : null
        );
      }

      const categoryRanks = [];

      for (
        let category = 0;
        category < categoryCount;
        category++
      ) {
        const targetAverage =
          simulatedAverages[category];

        if (targetAverage === null) {
          continue;
        }

        let rank = 1;

        for (
          let team = 0;
          team < teams.length;
          team++
        ) {
          if (team === targetTeamIndex) {
            continue;
          }

          const otherAverage =
            counts[team][category] > 0
              ? sums[team][category] /
                counts[team][category]
              : null;

          if (
            otherAverage !== null &&
            otherAverage > targetAverage
          ) {
            rank++;
          }
        }

        categoryRanks.push(rank);
      }

      const averageRank =
        categoryRanks.reduce(
          (sum, rank) => sum + rank,
          0
        ) / categoryRanks.length;

      stagedValues[candidateNumber][1] =
        averageRank;

      rankByName.set(candidateName, averageRank);
      completed++;
    }

    // Write every staged row at once.
    if (stagedValues.length > 0) {
      resultsSheet
        .getRange(1, 10, stagedValues.length + 1, 2)
        .setValues([
          ['Staged Player', 'Staged Average rank'],
          ...stagedValues
        ]);
    }

    // Build final output and sort by ascending average rank.
    const finalOutput = outputNames.map(name => {
      const rank = rankByName.get(name);

      return [
        name,
        rank ?? '',
        rank === undefined ? 'Outdated' : 'Complete'
      ];
    });

    finalOutput.sort((a, b) => {
      if (a[1] === '' && b[1] === '') return 0;
      if (a[1] === '') return 1;
      if (b[1] === '') return -1;
      return a[1] - b[1];
    });

    // Clear old A:C output and paste the sorted results.
    const rowsToClear = Math.max(
      oldDataLastRow - 1,
      finalOutput.length
    );

    if (rowsToClear > 0) {
      resultsSheet
        .getRange(2, 1, rowsToClear, 3)
        .clearContent();
    }

    if (finalOutput.length > 0) {
      resultsSheet
        .getRange(2, 1, finalOutput.length, 3)
        .setValues(finalOutput);
    }

    // Remove the staging columns after the final paste.
    resultsSheet.deleteColumns(10, 2);

    resultsSheet.getRange('E2').setValue(
      `${completed} of ${total} complete`
    );

    properties.deleteProperty('STOP_RANKINGS');
    stopCell.setValue(false);
  }

  /**
   * AR: added expected categories won this week.
   * AS: added probability of winning the full 14-category matchup this week.
   *
   * The matchup calculation assumes category outcomes are independent. A 7-7
   * result is counted as half a matchup win.
   */
  function calculateH2HPickupValues() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const players = ss.getSheetByName('Player Values - Cats');
    const h2h = ss.getSheetByName('H2H');
    const schedule = ss.getSheetByName('Schedule');

    if (!players || !h2h || !schedule) {
      throw new Error(
        'Expected Player Values - Cats, H2H, and Schedule sheets.'
      );
    }

    const sourceCategoryNames = [
      'G', 'A', '+/-', 'PIM', 'PPP', 'SHP', 'SOG',
      'FOW', 'HIT', 'BLK', 'W', 'GAA', 'SV%', 'SO'
    ];
    const rateCategoryIndexes = new Set([11, 12]); // GAA and SV%
    const firstDataRow = 3;
    const lastPlayerRow = players.getLastRow();

    const normalize = value => String(value ?? '').trim();
    const isFiniteNumber = value =>
      typeof value === 'number' && Number.isFinite(value);

    const playerHeaders = players
      .getRange(2, 1, 1, players.getLastColumn())
      .getDisplayValues()[0]
      .map(normalize);

    const columnFor = header => {
      const index = playerHeaders.indexOf(header);

      if (index === -1) {
        throw new Error(
          `Could not find the ${header} column in Player Values - Cats.`
        );
      }

      return index;
    };

    const statusColumn = columnFor('FTeam');
    const nhlTeamColumn = columnFor('TEAM');
    const categoryColumns = sourceCategoryNames.map(columnFor);

    // H2H I:V mirrors the fourteen category z-scores in Player Values - Cats.
    // W contains each player's number of NHL games in the selected matchup week.
    const myRoster = h2h.getRange(3, 9, 33, 15).getValues();
    const opponentRoster = h2h.getRange(39, 9, 33, 15).getValues();

    const rosterSummary = roster => {
      const result = sourceCategoryNames.map(() => ({
        weightedSum: 0,
        gameWeight: 0,
        gameSquares: 0
      }));

      roster.forEach(row => {
        const games = row[14];

        if (!isFiniteNumber(games) || games <= 0) return;

        for (let category = 0; category < 14; category++) {
          const value = row[category];

          // A blank goalie/skater category is not a z-score of zero. Ignoring
          // it prevents position-ineligible players from changing uncertainty.
          if (!isFiniteNumber(value)) continue;

          result[category].weightedSum += value * games;
          result[category].gameWeight += games;
          result[category].gameSquares += games * games;
        }
      });

      return result;
    };

    const myCurrent = rosterSummary(myRoster);
    const opponent = rosterSummary(opponentRoster);

    const categoryZScores = (mySummary, candidateValues, candidateGames) =>
      sourceCategoryNames.map((_, category) => {
        const mine = { ...mySummary[category] };
        const theirs = opponent[category];
        const candidateValue = candidateValues
          ? candidateValues[category]
          : null;

        if (
          isFiniteNumber(candidateValue) &&
          isFiniteNumber(candidateGames) &&
          candidateGames > 0
        ) {
          mine.weightedSum += candidateValue * candidateGames;
          mine.gameWeight += candidateGames;
          mine.gameSquares += candidateGames * candidateGames;
        }

        if (rateCategoryIndexes.has(category)) {
          if (mine.gameWeight === 0 || theirs.gameWeight === 0) return null;

          const myRate = mine.weightedSum / mine.gameWeight;
          const opponentRate = theirs.weightedSum / theirs.gameWeight;
          const variance =
            mine.gameSquares / (mine.gameWeight * mine.gameWeight) +
            theirs.gameSquares /
              (theirs.gameWeight * theirs.gameWeight);

          return variance > 0
            ? (myRate - opponentRate) / Math.sqrt(variance)
            : null;
        }

        const variance = mine.gameSquares + theirs.gameSquares;

        return variance > 0
          ? (mine.weightedSum - theirs.weightedSum) /
            Math.sqrt(variance)
          : null;
      });

    const normalCdf = z => {
      // Abramowitz and Stegun 7.1.26; accurate to better than 7.5e-8.
      const sign = z < 0 ? -1 : 1;
      const x = Math.abs(z) / Math.sqrt(2);
      const t = 1 / (1 + 0.3275911 * x);
      const erf = 1 - (((((1.061405429 * t - 1.453152027) * t +
        1.421413741) * t - 0.284496736) * t + 0.254829592) * t) *
        Math.exp(-x * x);

      return 0.5 * (1 + sign * erf);
    };

    const probabilities = zScores => zScores.map(z =>
      isFiniteNumber(z) ? normalCdf(z) : 0.5
    );

    const matchupWinProbability = categoryProbabilities => {
      let distribution = [1];

      categoryProbabilities.forEach(probability => {
        const next = Array(distribution.length + 1).fill(0);

        distribution.forEach((chance, wins) => {
          next[wins] += chance * (1 - probability);
          next[wins + 1] += chance * probability;
        });

        distribution = next;
      });

      const tieWins = categoryProbabilities.length / 2;
      let result = distribution[tieWins] * 0.5;

      for (let wins = tieWins + 1; wins < distribution.length; wins++) {
        result += distribution[wins];
      }

      return result;
    };

    const scheduleHeaders = schedule
      .getRange(31, 1, 1, schedule.getLastColumn())
      .getDisplayValues()[0]
      .map(normalize);
    const remainingGamesColumn = scheduleHeaders.indexOf(
      'Games remaining this week'
    );

    if (remainingGamesColumn === -1) {
      throw new Error(
        'Could not find the Games remaining this week column in Schedule row 31. '
        + 'Run the updateschedule command first.'
      );
    }

    const scheduleRows = schedule
      .getRange(
        32,
        1,
        schedule.getLastRow() - 31,
        remainingGamesColumn + 1
      )
      .getValues();
    const gamesByTeam = new Map();

    scheduleRows.forEach(row => {
      const team = normalize(row[0]);
      const games = row[remainingGamesColumn];

      if (team !== '' && isFiniteNumber(games)) {
        gamesByTeam.set(team, games);
      }
    });

    const currentProbabilities = probabilities(
      categoryZScores(myCurrent, null, null)
    );
    const currentExpectedCategories = currentProbabilities.reduce(
      (sum, probability) => sum + probability,
      0
    );
    const currentMatchupWin = matchupWinProbability(currentProbabilities);

    const outputColumn = 44; // AR
    players.getRange(2, outputColumn, 1, 2).setValues([[
      'Δ Expected Cats Won',
      'Δ Matchup Win %'
    ]]);

    if (lastPlayerRow < firstDataRow) return;

    const playerRows = players
      .getRange(
        firstDataRow,
        1,
        lastPlayerRow - firstDataRow + 1,
        players.getLastColumn()
      )
      .getValues();

    const output = playerRows.map(row => {
      if (normalize(row[statusColumn]) !== 'Undrafted') {
        return ['', ''];
      }

      const candidateGames = gamesByTeam.get(
        normalize(row[nhlTeamColumn])
      ) ?? 0;
      const candidateValues = categoryColumns.map(column => row[column]);
      const addedProbabilities = probabilities(
        categoryZScores(myCurrent, candidateValues, candidateGames)
      );
      const addedExpectedCategories = addedProbabilities.reduce(
        (sum, probability) => sum + probability,
        0
      );
      const addedMatchupWin = matchupWinProbability(addedProbabilities);

      return [
        addedExpectedCategories - currentExpectedCategories,
        addedMatchupWin - currentMatchupWin
      ];
    });

    players
      .getRange(firstDataRow, outputColumn, output.length, 2)
      .setValues(output)
      .setNumberFormats(Array(output.length).fill(['0.000', '0.0%']));
  }

  /**
   * Find one-for-one trades where each side improves in at least one category.
   * A straight swap cannot improve both teams' average ranking simultaneously,
   * so the results prioritize balanced category gains and show the ranking cost
   * (or benefit) for both managers explicitly. Category changes are team
   * average z-score deltas, matching the values in Roster Comparison.
   */
  function findTrades() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const playersSheet = ss.getSheetByName('Player Values - Cats');
    const comparisonSheet = ss.getSheetByName('Roster Comparison');
    const resultsSheet = ss.getSheetByName('Trade Finder');

    if (!playersSheet || !comparisonSheet || !resultsSheet) {
      throw new Error(
        'Expected Player Values - Cats, Roster Comparison, and Trade Finder sheets.'
      );
    }

    const myTeam = 'Rob/Orad';
    const firstDataRow = 3;
    const categoryNames = [
      'G', 'A', '+/-', 'PIM', 'PPP', 'SHP', 'SOG',
      'FOW', 'HIT', 'BLK', 'W', 'GAA', 'SV%', 'SO'
    ];
    const minimumCategoryChange = 0.01;
    const minimumMyRankImprovement = -0.01;
    const normalize = value => String(value ?? '').trim();
    const isFiniteNumber = value =>
      typeof value === 'number' && Number.isFinite(value);

    const headers = playersSheet
      .getRange(2, 1, 1, playersSheet.getLastColumn())
      .getDisplayValues()[0]
      .map(normalize);
    const columnFor = header => {
      const index = headers.indexOf(header);
      if (index === -1) {
        throw new Error(
          `Could not find the ${header} column in Player Values - Cats.`
        );
      }
      return index;
    };

    const rankingColumn = columnFor('New ranking');
    const vorpColumn = columnFor('VORP');
    const ownerColumn = columnFor('FTeam');
    const nameColumn = columnFor('PLAYER');
    const positionColumn = columnFor('POS');
    const performanceColumn = columnFor('Season vs Projection Δ');
    const categoryColumns = categoryNames.map(columnFor);
    const rosterTeams = new Set(
      comparisonSheet.getRange('A6:A13').getDisplayValues().flat()
        .map(normalize)
        .filter(Boolean)
    );
    const rows = playersSheet
      .getRange(
        firstDataRow,
        1,
        playersSheet.getLastRow() - firstDataRow + 1,
        playersSheet.getLastColumn()
      )
      .getValues();
    const byTeam = new Map();
    const availablePlayers = [];

    rows.forEach(row => {
      const owner = normalize(row[ownerColumn]);
      const name = normalize(row[nameColumn]);
      const ranking = row[rankingColumn];
      const vorp = row[vorpColumn];
      const positions = normalize(row[positionColumn]).split(',').map(
        position => position.trim()
      );

      if (name === '' || !isFiniteNumber(ranking)) {
        return;
      }
      const player = {
        name,
        ranking,
        vorp: isFiniteNumber(vorp) ? vorp : null,
        isGoalie: positions.includes('G'),
        seasonVsProjection: isFiniteNumber(row[performanceColumn])
          ? row[performanceColumn]
          : null,
        // Keep non-applicable skater/goalie categories blank. Roster
        // Comparison's AVERAGEIFS excludes those cells, so the trade math must
        // exclude them too rather than treating them as a zero z-score.
        categories: categoryColumns.map(column =>
          isFiniteNumber(row[column]) ? row[column] : null
        )
      };

      if (owner === 'Undrafted') {
        availablePlayers.push(player);
      } else if (rosterTeams.has(owner)) {
        if (!byTeam.has(owner)) {
          byTeam.set(owner, []);
        }
        byTeam.get(owner).push(player);
      }
    });

    const myPlayers = byTeam.get(myTeam) || [];
    if (myPlayers.length === 0) {
      throw new Error(`No ranked players were found for ${myTeam}.`);
    }

    const average = teamPlayers =>
      teamPlayers.reduce((sum, player) => sum + player.ranking, 0) /
      teamPlayers.length;
    const categoryAverages = teamPlayers => categoryNames.map((_, index) => {
      let sum = 0;
      let count = 0;

      teamPlayers.forEach(player => {
        const value = player.categories[index];
        if (isFiniteNumber(value)) {
          sum += value;
          count++;
        }
      });

      return { sum, count, average: count > 0 ? sum / count : null };
    });
    const hasCategoryValue = player =>
      player.categories.some(isFiniteNumber);
    const categoryDeltas = (before, after) => before.map((category, index) => {
      const afterCategory = after[index];
      // If one roster has no players for a category before or after the
      // transaction, Roster Comparison shows it as blank, so do not claim a
      // gain.
      return category.average === null || afterCategory.average === null
        ? 0
        : afterCategory.average - category.average;
    });
    const abbreviatedName = name => {
      const parts = normalize(name).split(/\s+/).filter(Boolean);
      if (parts.length < 2) return normalize(name);
      const surname = parts.pop();
      const initials = parts.map(part => part.split('-').map(
        segment => `${segment.charAt(0)}.`
      ).join('-')).join(' ');
      return `${initials} ${surname}`;
    };
    const followUpText = followUp => {
      if (!followUp.drop) return '';
      return `- ${abbreviatedName(followUp.drop.name)}; + ${abbreviatedName(followUp.add.name)}`;
    };
    const applyTradeWithRosterMove = (teamPlayers, sent, received) => {
      const afterTrade = teamPlayers.filter(player => player !== sent);
      afterTrade.push(received);
      if (sent.isGoalie === received.isGoalie) {
        return { players: afterTrade, drop: null, add: null };
      }

      // A cross-position swap overfills received's position and leaves a hole
      // at sent's position. Model the actual cleanup using player value: drop
      // the lowest-VORP *existing* player at the overfull position, then add
      // the highest-VORP available player at the newly open position. New
      // ranking is a team-category measure, not a cut-value measure.
      const dropCandidates = teamPlayers.filter(player =>
        player !== sent && player.isGoalie === received.isGoalie &&
        hasCategoryValue(player) && isFiniteNumber(player.vorp)
      ).sort((left, right) => left.vorp - right.vorp);
      const addCandidates = availablePlayers.filter(player =>
        player.isGoalie === sent.isGoalie && hasCategoryValue(player) &&
        isFiniteNumber(player.vorp)
      ).sort((left, right) => right.vorp - left.vorp);
      const drop = dropCandidates[0];
      const add = addCandidates[0];
      if (!drop || !add) return null;

      return {
        players: afterTrade.filter(player => player !== drop).concat(add),
        drop,
        add
      };
    };
    const noTradeBaseline = (teamPlayers, sent, received) => {
      if (sent.isGoalie === received.isGoalie) {
        return { players: teamPlayers, drop: null, add: null };
      }

      // Compare a cross-position trade with the no-trade roster move that
      // creates the same positional shape. This removes any independent
      // waiver value (for example, cutting Binnington for Olivier) from the
      // trade score, leaving only the value caused by sent -> received.
      const dropCandidates = teamPlayers.filter(player =>
        player.isGoalie === received.isGoalie && hasCategoryValue(player) &&
        isFiniteNumber(player.vorp)
      ).sort((left, right) => left.vorp - right.vorp);
      const addCandidates = availablePlayers.filter(player =>
        player.isGoalie === sent.isGoalie && hasCategoryValue(player) &&
        isFiniteNumber(player.vorp)
      ).sort((left, right) => right.vorp - left.vorp);
      const drop = dropCandidates[0];
      const add = addCandidates[0];
      if (!drop || !add) return null;
      return {
        players: teamPlayers.filter(player => player !== drop).concat(add),
        drop,
        add
      };
    };
    const categorySummary = deltas => {
      let netScore = 0;
      const rankedChanges = deltas.map((delta, index) => {
        // Score every category change, even tiny ones, so a trade's score is
        // its net team-category gain rather than a sum of gains only.
        netScore += delta;
        return { delta, index, magnitude: Math.abs(delta) };
      });
      const displayed = rankedChanges.filter(
        change => change.magnitude > minimumCategoryChange
      );

      // Keep small but meaningful trade effects visible when fewer than three
      // categories clear the threshold.
      rankedChanges.sort((left, right) => right.magnitude - left.magnitude)
        .some(change => {
          if (displayed.length >= 3) return true;
          if (!displayed.some(item => item.index === change.index)) {
            displayed.push(change);
          }
          return false;
        });
      displayed.sort((left, right) => right.magnitude - left.magnitude);
      const text = displayed.map(change =>
        `${categoryNames[change.index]} ${change.delta >= 0 ? '+' : ''}${change.delta.toFixed(3)}`
      ).join(', ');

      return { text, score: netScore };
    };
    const trades = [];

    byTeam.forEach((partnerPlayers, partner) => {
      if (partner === myTeam || partnerPlayers.length === 0) {
        return;
      }

      myPlayers.forEach(sent => {
        partnerPlayers.forEach(received => {
          const myFollowUp = applyTradeWithRosterMove(myPlayers, sent, received);
          const partnerFollowUp = applyTradeWithRosterMove(
            partnerPlayers, received, sent
          );
          const myBaseline = noTradeBaseline(myPlayers, sent, received);
          const partnerBaseline = noTradeBaseline(
            partnerPlayers, received, sent
          );
          if (!myFollowUp || !partnerFollowUp || !myBaseline || !partnerBaseline) return;
          const myDeltas = categoryDeltas(
            categoryAverages(myBaseline.players), categoryAverages(myFollowUp.players)
          );
          const partnerDeltas = categoryDeltas(
            categoryAverages(partnerBaseline.players),
            categoryAverages(partnerFollowUp.players)
          );
          const myCategories = categorySummary(myDeltas);
          const partnerCategories = categorySummary(partnerDeltas);

          // Category complementarity is what can make a one-for-one trade
          // appealing to both teams; a scalar ranking alone is zero-sum.
          const myAverage = average(myBaseline.players);
          const partnerAverage = average(partnerBaseline.players);
          const newMyAverage = average(myFollowUp.players);
          const newPartnerAverage = average(partnerFollowUp.players);
          const myImprovement = myAverage - newMyAverage;
          const partnerImprovement = partnerAverage - newPartnerAverage;
          if (myImprovement < minimumMyRankImprovement) {
            return;
          }
          const balancedScore = Math.min(
            myCategories.score,
            partnerCategories.score
          );
          const tradeType = sent.isGoalie && received.isGoalie
            ? 'Goalie ↔ Goalie'
            : sent.isGoalie || received.isGoalie
              ? 'Goalie ↔ Skater'
              : 'Skater ↔ Skater';

          trades.push({
            partner,
            sent,
            received,
            myFollowUp,
            partnerFollowUp,
            tradeType,
            myAverage,
            newMyAverage,
            myImprovement,
            partnerAverage,
            newPartnerAverage,
            partnerImprovement,
            myCategories,
            partnerCategories,
            balancedScore
          });
        });
      });
    });

    const compareTrades = (left, right) =>
      right.myCategories.score - left.myCategories.score ||
      left.newMyAverage - right.newMyAverage;
    const compareByBalancedScore = (left, right) =>
      right.balancedScore - left.balancedScore ||
      right.myCategories.score - left.myCategories.score ||
      left.newMyAverage - right.newMyAverage;

    const tradeMix = [
      { type: 'Goalie ↔ Goalie', limit: 5 },
      { type: 'Goalie ↔ Skater', limit: 5 },
      { type: 'Skater ↔ Skater', limit: 40 }
    ];
    const paretoFrontier = candidates => candidates.filter(candidate =>
      !candidates.some(other => {
        if (other === candidate) return false;

        const noWorse =
          other.myCategories.score >= candidate.myCategories.score &&
          other.partnerCategories.score >= candidate.partnerCategories.score &&
          other.myImprovement >= candidate.myImprovement;
        const strictlyBetter =
          other.myCategories.score > candidate.myCategories.score ||
          other.partnerCategories.score > candidate.partnerCategories.score ||
          other.myImprovement > candidate.myImprovement;

        return noWorse && strictlyBetter;
      })
    );
    const topTrades = tradeMix.flatMap(({ type, limit }) =>
      paretoFrontier(trades.filter(trade => trade.tradeType === type))
        .sort(compareByBalancedScore)
        .slice(0, limit)
    ).sort(compareTrades);

    const outputHeaders = [
      'Rank', 'Partner', 'You Send', 'Projection Δ',
      'You Receive', 'Projection Δ',
      'New Avg Rank', 'Avg Rank Δ',
      'Net Category Score', 'Partner Net Category Score',
      'Category Changes', 'Partner Category Changes',
      'Balanced Trade Score', 'Your Follow-up', 'Partner Follow-up'
    ];
    const output = topTrades.map((trade, index) => [
      index + 1, trade.partner, trade.sent.name, trade.sent.seasonVsProjection,
      trade.received.name, trade.received.seasonVsProjection,
      trade.newMyAverage, trade.myImprovement,
      trade.myCategories.score, trade.partnerCategories.score,
      trade.myCategories.text, trade.partnerCategories.text,
      trade.balancedScore, followUpText(trade.myFollowUp),
      followUpText(trade.partnerFollowUp)
    ]);

    resultsSheet.getRange(
      1, 1, resultsSheet.getMaxRows(), resultsSheet.getMaxColumns()
    ).breakApart();
    resultsSheet.getDataRange().clearContent();
    resultsSheet.getRange(1, 1, 1, outputHeaders.length)
      .setValues([outputHeaders]);

    if (output.length > 0) {
      resultsSheet.getRange(2, 1, output.length, outputHeaders.length)
        .setValues(output);
      resultsSheet.getRange(2, 4, output.length, 1)
        .setNumberFormat('+0.000;-0.000;0.000');
      resultsSheet.getRange(2, 6, output.length, 1)
      .setNumberFormat('+0.000;-0.000;0.000');
      resultsSheet.getRange(2, 7, output.length, 4)
        .setNumberFormat('0.000');
      resultsSheet.getRange(2, 13, output.length, 1)
        .setNumberFormat('0.000');
      const goalieRowColor = '#fff2cc';
      resultsSheet.getRange(2, 1, output.length, outputHeaders.length)
        .setBackgrounds(topTrades.map(trade => Array(outputHeaders.length).fill(
          trade.sent.isGoalie || trade.received.isGoalie ? goalieRowColor : '#ffffff'
        )));
    } else {
      resultsSheet.getRange('A2').setValue(
        'No eligible one-for-one trades were found.'
      );
    }

    resultsSheet.getRange('A1:O1').setFontWeight('bold')
      .setBackground('#d9eaf7');
    resultsSheet.autoResizeColumns(1, outputHeaders.length);
    resultsSheet.setFrozenRows(1);
  }

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

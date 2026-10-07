  function onOpen() {
    SpreadsheetApp.getUi()
      .createMenu('Fantasy Helper')
      .addItem(
        'Recalculate undrafted player rankings',
        'rankAllUndraftedPlayers'
      )
      .addItem(
        'Recalculate all player rankings',
        'rankAllPlayers'
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

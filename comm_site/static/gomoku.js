// DOM (HTML) の読み込みが完了したら実行
document.addEventListener('DOMContentLoaded', () => {

    // (socket 変数は base.html で既に定義されているはず)
    // const socket = io(); 

    const boardElement = document.getElementById('gomoku-board');
    const statusElement = document.getElementById('game-status');
    const opponentNameElement = document.getElementById('opponent-name');
    const playerInfoElement = document.getElementById('player-info');
    
    const gameOverModal = document.getElementById('game-over-modal');
    const gameOverTitle = document.getElementById('game-over-title');
    const gameOverMessage = document.getElementById('game-over-message');

    let currentRoomId = null;
    let myColor = null;
    let myTurn = false;
    // JS側でも碁盤の状態を管理
    let boardState = Array(15).fill(null).map(() => Array(15).fill(null)); 

    // 1. 15x15 の碁盤のマス目を生成
    for (let r = 0; r < 15; r++) {
        for (let c = 0; c < 15; c++) {
            let cell = document.createElement('div');
            // 碁盤の線（中心線）を描画するためのクラスを追加
            cell.className = 'gomoku-cell';
            cell.dataset.row = r;
            cell.dataset.col = c;
            
            // 盤の交点に点を打つ（装飾）
            if ((r === 3 || r === 7 || r === 11) && (c === 3 || c === 7 || c === 11)) {
                 cell.classList.add('star-point');
            }

            // 各マス目にクリックイベントを追加
            cell.addEventListener('click', () => {
                // ゲームが始まっていて、かつ自分のターンの場合
                if (currentRoomId && myTurn) {
                    // まだ石が置かれていないマスか確認
                    if (boardState[r][c] === null) {
                        // サーバーに「ここに石を置く」と通知
                        socket.emit('make_gomoku_move', {
                            room_id: currentRoomId,
                            row: r,
                            col: c
                        });
                        myTurn = false; // 石を置いたらターン終了
                        statusElement.textContent = '相手のターンです';
                        statusElement.classList.remove('text-kawaii-pink', 'animate-pulse');
                    }
                }
            });
            boardElement.appendChild(cell);
        }
    }
    
    // style.css に以下の CSS を追加する必要があります：
    // .gomoku-cell { width: 40px; height: 40px; border: 1px solid #B19CD9; background-color: #FFD1A1; cursor: pointer; position: relative; }
    // .gomoku-cell:hover { background-color: #FF88B6; }
    // .star-point::after { content: ''; width: 6px; height: 6px; background: #4A4A4A; border-radius: 50%; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); }


    // 2. ページを開いたらすぐにゲーム検索を開始
    socket.emit('find_gomoku_game');
    statusElement.textContent = '対戦相手を探しています...';

    // --- SocketIO ： サーバーからのイベントを監視 (Listen) ---

    // 監視：サーバーからのステータス更新 (例：待機中)
    socket.on('gomoku_status', (data) => {
        statusElement.textContent = data.message;
    });

    // 監視：ゲーム開始！
    socket.on('gomoku_game_start', (data) => {
        currentRoomId = data.room_id;
        myColor = data.your_color;
        opponentNameElement.textContent = data.opponent_name;
        
        // 自分の情報を更新 (黒か白か)
        // (currentUserName は gomoku.html で定義)
        playerInfoElement.innerHTML = `
            <p class="font-bold text-lg">あなた (${myColor === 'black' ? '黒' : '白'}):</p>
            <p>${currentUserName}</p>
        `;
        
        // 最初のターンを判定 (currentUserId は gomoku.html で定義)
        myTurn = (data.turn === currentUserId); 
        updateTurnIndicator();
    });

    // 監視：誰かが石を置いた
    socket.on('gomoku_move_made', (data) => {
        // 1. JS側の碁盤を更新
        boardState[data.row][data.col] = data.color;
        
        // 2. 画面に石を描画
        drawStone(data.row, data.col, data.color);
    });

    // 監視：ターンの更新
    socket.on('gomoku_turn_update', (data) => {
        // (currentUserId は gomoku.html で定義)
        myTurn = (data.turn === currentUserId); 
        updateTurnIndicator();
    });

    // 監視：ゲーム終了
    socket.on('gomoku_game_over', (data) => {
        myTurn = false;
        currentRoomId = null; // ゲーム終了

        gameOverTitle.textContent = data.winner_name + " の勝利！";
        
        // 自分が勝者か敗者かでメッセージを変える
        if (data.winner_id === currentUserId) {
            gameOverMessage.textContent = `おめでとうございます！ (スコア: ${data.winner_score} [+10])`;
        } else {
            gameOverMessage.textContent = `残念でした... (スコア: ${data.loser_score} [-5])`;
        }

        gameOverModal.style.display = 'flex';
    });
    
    // 監視：サーバーからのエラー
    socket.on('gomoku_error', (data) => {
        alert(data.message);
        // ターンを戻す（もしあれば）
        updateTurnIndicator();
    });

    // --- ヘルパー関数 ---

    // 石を描画する関数
    function drawStone(row, col, color) {
        const cell = boardElement.querySelector(`[data-row='${row}'][data-col='${col}']`);
        if (cell) {
            let stone = document.createElement('div');
            // CSSで石のスタイルを調整 (w-full h-full でマスいっぱいに)
            stone.className = 'w-full h-full rounded-full shadow-md transform scale-90'; 
            if (color === 'black') {
                stone.classList.add('bg-black');
            } else {
                stone.classList.add('bg-white', 'border-2', 'border-gray-400');
            }
            cell.innerHTML = ''; // マスをクリア (重複防止)
            cell.appendChild(stone);
            cell.style.cursor = 'not-allowed';
        }
    }

    // ターン表示を更新する関数
    function updateTurnIndicator() {
        if (myTurn) {
            statusElement.textContent = 'あなたのターンです';
            statusElement.classList.add('text-kawaii-pink', 'animate-pulse');
        } else {
            statusElement.textContent = '相手のターンです';
            statusElement.classList.remove('text-kawaii-pink', 'animate-pulse');
        }
    }
});
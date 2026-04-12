import { TournamentBoard } from './components/TournamentBoard.js';
class App {
    constructor() {
        this.tournamentBoard = new TournamentBoard('tournamentBoard', 'tourSelect');
    }
}
document.addEventListener('DOMContentLoaded', () => {
    new App();
});

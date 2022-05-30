# Debaterating
#### Video Demo:  <URL HERE>
#### Description:
The goal of this website is to calculate show a rating of Russian British Parliamentary debaters and record the results of Russian BP tournaments. BP debating is an intellectual sport where participants are given a motion related to an important societal, political, economic or philosophical question and are asked to deliver arguments in support of the side they have been allocated to.

BP tournaments require complex tabulation to observe power pairing rules, prevent teams from being allocated to the same role multiple times and observe other rules. This is normally done with the use of Tabbycat software. My web application uses Tabbycat API to export multiple types of data from tournament instances (participants, participant categories, rounds, individual debates, team performances, individual speeches, etc.), with ~800 rows of data per tournament. This data is then validated by the admin and transformed into the format that my application uses, to be used in various views and dashboards. An ELO rating is calculated for all the tournament participants.

The views that I've made include a speaker rating, a list of tournaments, a dashboard with various charts exploring speaker performance and a dashboard showing the result of the tournament and 
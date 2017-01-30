# backant
ANTRace Backend (with mesh-network)

## Websocket API
#### Browser -> Backend:
Start Race: `{"StartRace": true}` // you can put anything in the place of `true`, it will be ignored  
Stop Race: `{"StopRace": true}` // you can put anything in the place of `true`, it will be ignored  
Set Difficulty: `{"SetDifficulty": "easy"}` // you can use `easy`/`hard` to set the difficulty of the current bike  
#### Backend -> Browser:
Start Race: `{"StartRace": 12345}` // Bike 12345 has initiated the start of a race. We should start as well.  
Stop Race: `{"StopRace": 12345}` // Bike 12345 has initiated the stop of a race. We should stop as well.  
Update: `{"Update": {12345: {"power": 500, "cadence": 300, "speed": 200}}}` // This is the general format of an update message. The message can contain any combination of power speed and cadence, for any number of bikes.

# Configuration

There are three main configuration files placed in /etc/pqopen/ directory.

| File             | Configuration for                                            |
| ---------------- | ------------------------------------------------------------ |
| daqinfo.toml     | daqopen-zmq-server<br />Information about the ACQ system, inputs and zmq server |
| pqopen-conf.toml | pqopen<br />Power system information and phases. Storing Endpoints |
| persistmq.conf   | persistmq-bridge<br />Source and target of the MQTT messages; Cache-file |


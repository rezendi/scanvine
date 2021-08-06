//worker.ts
import { connect, Channel, Connection, ConsumeMessage } from 'amqplib';

export default class VortextWorker {
  private connection?: Connection;
  private channel?: Channel;
  private queueName = 'vortext-jobs';
  constructor() {
    this.initializeService();
  }

  private async initializeService() {
    try {
      console.log("hi");
      await this.initializeConnection();
      await this.initializeChannel();
      await this.initializeQueues();
      await this.startConsuming();
    } catch (err) {
      console.error(err);
    }
  }
  private async initializeConnection() {
    try {
      console.log("rabbitmq url ", process.env.RABBITMQ_URL)
      this.connection = await connect(process.env.RABBITMQ_URL || 'amqp://localhost:5432');
      console.info('Connected to RabbitMQ Server');
    } catch (err) {
      throw err;
    }
  }

  private async initializeChannel() {
    try {
      this.channel = await this.connection?.createChannel();
      console.info('Created RabbitMQ Channel');
    } catch (err) {
      throw err;
    }
  }

  private async initializeQueues() {
    try {
      await this.channel?.assertQueue(this.queueName, {
        durable: true,
      });
      console.info('Initialized RabbitMQ Queues');
    } catch (err) {
      throw err;
    }
  }

  public async startConsuming() {
    this.channel?.prefetch(1);
    console.info(' 🚀 Waiting for messages in %s. To exit press CTRL+C', this.queueName);
    this.channel?.consume(
      this.queueName,
      async (msg: ConsumeMessage | null) => {
        if (msg) {
          console.log("Received new msg", msg.content.toString());
          try {
            let success = await this.handleJob(msg);
            success ? this.channel?.ack(msg) : this.channel?.reject(msg, false);;
          } catch (err) {
            console.error('Failed to process msg', msg, err);
            this.channel?.reject(msg, false);
          }
        }
      },
      {
        noAck: false,
      },
    );
  }

  public async handleJob(job:any) {
    console.log("Handling job", job.content.toString());
    return Promise.resolve(true);
  }
}

if (require.main === module) {
  main();
}

async function main() {
  let worker = new VortextWorker();
  worker.startConsuming();
}

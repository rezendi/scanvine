import amqp, { Channel, Connection } from 'amqplib';

export class RabbitMQService {
  private connection?: Connection;
  private channel?: Channel;
  private queueName = 'vortext-jobs';
  constructor() {
    this.initializeService();
  }

  private async initializeService() {
    try {
      console.log('Initializing Vortext RabbitMQ Service');
      await this.initializeConnection();
      await this.initializeChannel();
      await this.initializeQueues();
    } catch (err) {
        console.log('Error', err);
    }
  }
  private async initializeConnection() {
    try {
      this.connection = await amqp.connect(process.env.RABBITMQ_URL!);
      console.log('Connected to Vortext RabbitMQ Server');
    } catch (err) {
      throw err;
    }
  }

  private async initializeChannel() {
    try {
      this.channel = await this.connection?.createChannel();
      console.log('Created Vortext RabbitMQ Channel');
    } catch (err) {
      throw err;
    }
  }
  private async initializeQueues() {
    try {
      await this.channel?.assertQueue(this.queueName, {
        durable: true,
      });
     console.log('Initialized Vortext RabbitMQ Queues');
    } catch (err) {
      throw err;
    }
  }

  public async sendToQueue(message: string) {
    this.channel?.sendToQueue(this.queueName, Buffer.from(message), {
      persistent: true,
    });
    console.log(`sent: ${message} to queue ${this.queueName}`);
  }
}

export var RabbitMQ = new RabbitMQService();

# Databricks notebook source
# MAGIC %run ./Classroom-Setup-Common

# COMMAND ----------

@DBAcademyHelper.add_method
def register_model(self, model_uri, catalog_name, schema_name):
    import mlflow

    print("Registering fallback model with a unique name based on username...")

    try:
        suffix = self.username.split("_")[-1].split("@")[0]
    except Exception:
        raise ValueError("Could not extract suffix from DA.username. Ensure it follows the expected format.")

    model_name = f"{catalog_name}.{schema_name}.rag_app_{suffix}"

    # Register a clone of the original model under this new name
    mlflow.set_registry_uri("databricks-uc")
    mlflow.register_model(model_uri, model_name)

    print(f"Successfully registered model: {model_name}")
    return model_name

# COMMAND ----------

DA = DBAcademyHelper()
DA.init()

# COMMAND ----------

import pandas as pd
from io import StringIO

eval_set = """request,expected_response,evolution_type,episode_done
"What are the limitations of symbolic planning in task and motion planning, and how can leveraging large language models help overcome these limitations?","Symbolic planning in task and motion planning can be limited by the need for explicit primitives and constraints. Leveraging large language models can help overcome these limitations by enabling the robot to use language models for planning and execution, and by providing a way to extract and leverage knowledge from large language models to solve temporally extended tasks.",simple,TRUE
"What are some techniques used to fine-tune transformer models for personalized code generation, and how effective are they in improving prediction accuracy and preventing runtime errors? ","The techniques used to fine-tune transformer models for personalized code generation include ﬁne-tuning transformer models, adopting a novel approach called Target Similarity Tuning (TST) to retrieve a small set of examples from a training bank, and utilizing these examples to train a pretrained language model. The effectiveness of these techniques is shown in the improvement in prediction accuracy and the prevention of runtime errors.",simple,TRUE
How does the PPO-ptx model mitigate performance regressions in the few-shot setting?,"The PPO-ptx model mitigates performance regressions in the few-shot setting by incorporating pre-training and fine-tuning on the downstream task. This approach allows the model to learn generalizable features and adapt to new tasks more effectively, leading to improved few-shot performance.",simple,TRUE
How can complex questions be decomposed using successive prompting?,"Successive prompting is a method for decomposing complex questions into simpler sub-questions, allowing language models to answer them more accurately. This approach was proposed by Dheeru Dua, Shivanshu Gupta, Sameer Singh, and Matt Gardner in their paper 'Successive Prompting for Decomposing Complex Questions', presented at EMNLP 2022.",simple,TRUE
"Which entity type in Named Entity Recognition is likely to be involved in information extraction, question answering, semantic parsing, and machine translation?",Organization,reasoning,TRUE
What is the purpose of ROUGE (Recall-Oriented Understudy for Gisting Evaluation) in automatic evaluation methods?,"ROUGE (Recall-Oriented Understudy for Gisting Evaluation) is used in automatic evaluation methods to evaluate the quality of machine translation. It calculates N-gram co-occurrence statistics, which are used to assess the similarity between the candidate text and the reference text. ROUGE is based on recall, whereas BLEU is based on accuracy.",simple,TRUE
"What are the challenges associated with Foundation SSL in CV, and how do they relate to the lack of theoretical foundation, semantic understanding, and explicable exploration?","The challenges associated with Foundation SSL in CV include the lack of a profound theory to support all kinds of tentative experiments, and further exploration has no handbook. The pretrained LM may not learn the meaning of the language, relying on corpus learning instead. The models cannot reach a better level of stability and match different downstream tasks, and the primary method is to increase data, improve computation power, and design training procedures to achieve better results. The lack of theoretical foundation, semantic understanding, and explicable exploration are the main challenges in Foundation SSL in CV.",simple,TRUE
How does ChatGPT handle factual input compared to GPT-3.5?,"ChatGPT handles factual input better than GPT-3.5, with a 21.9% increase in accuracy when the premise entails the hypothesis. This is possibly related to the preference for human feedback in ChatGPT's RLHF design during model training.",simple,TRUE
What are some of the challenges in understanding natural language commands for robotic navigation and mobile manipulation?,"Some challenges in understanding natural language commands for robotic navigation and mobile manipulation include integrating natural language understanding with reinforcement learning, understanding natural language directions for robotic navigation, and mapping instructions and visual observations to actions with reinforcement learning.",simple,TRUE
"How does chain of thought prompting elicit reasoning in large language models, and what are the potential applications of this technique in neural text generation and human-AI interaction?","The context discusses the use of chain of thought prompting to elicit reasoning in large language models, which can be applied in neural text generation and human-AI interaction. Specifically, researchers have used this technique to train language models to generate coherent and contextually relevant text, and to create transparent and controllable human-AI interaction systems. The potential applications of this technique include improving the performance of language models in generating contextually appropriate responses, enhancing the interpretability and controllability of AI systems, and facilitating more effective human-AI collaboration.",simple,TRUE
"Using the given context, how can the robot be instructed to move objects around on a tabletop to complete rearrangement tasks?","The robot can be instructed to move objects around on a tabletop to complete rearrangement tasks by using natural language instructions that specify the objects to be moved and their desired locations. The instructions can be parsed using functions such as parse_obj_name and parse_position to extract the necessary information, and then passed to a motion primitive that can pick up and place objects in the specified locations. The get_obj_names and get_obj_pos APIs can be used to access information about the available objects and their locations in the scene.",reasoning,TRUE
"How can searching over an organization's existing knowledge, data, or documents using LLM-powered applications reduce the time it takes to complete worker activities?","Using AI tools to search through a company's information can significantly cut down the time workers need to finish tasks. These tools quickly find and provide the necessary details by scanning large amounts of data efficiently.",simple,TRUE
"""

obj = StringIO(eval_set)
DA.eval_df = pd.read_csv(obj)

# COMMAND ----------

# Create evaluation dataset in new MLflow evaluation format

DA.eval_dataset = [
    {
        "inputs": {"request": "What are the limitations of symbolic planning in task and motion planning, and how can leveraging large language models help overcome these limitations?"},
        "expectations": {"expected_response": "Symbolic planning in task and motion planning can be limited by the need for explicit primitives and constraints. Leveraging large language models can help overcome these limitations by enabling the robot to use language models for planning and execution, and by providing a way to extract and leverage knowledge from large language models to solve temporally extended tasks."}
    },
    {
        "inputs": {"request": "What are some techniques used to fine-tune transformer models for personalized code generation, and how effective are they in improving prediction accuracy and preventing runtime errors?"},
        "expectations": {"expected_response": "The techniques used to fine-tune transformer models for personalized code generation include fine-tuning transformer models, adopting a novel approach called Target Similarity Tuning (TST) to retrieve a small set of examples from a training bank, and utilizing these examples to train a pretrained language model. The effectiveness of these techniques is shown in the improvement in prediction accuracy and the prevention of runtime errors."}
    },
    {
        "inputs": {"request": "How does the PPO-ptx model mitigate performance regressions in the few-shot setting?"},
        "expectations": {"expected_response": "The PPO-ptx model mitigates performance regressions in the few-shot setting by incorporating pre-training and fine-tuning on the downstream task. This approach allows the model to learn generalizable features and adapt to new tasks more effectively, leading to improved few-shot performance."}
    },
    {
        "inputs": {"request": "How can complex questions be decomposed using successive prompting?"},
        "expectations": {"expected_response": "Successive prompting is a method for decomposing complex questions into simpler sub-questions, allowing language models to answer them more accurately. This approach was proposed by Dheeru Dua, Shivanshu Gupta, Sameer Singh, and Matt Gardner in their paper 'Successive Prompting for Decomposing Complex Questions', presented at EMNLP 2022."}
    },
    {
        "inputs": {"request": "Which entity type in Named Entity Recognition is likely to be involved in information extraction, question answering, semantic parsing, and machine translation?"},
        "expectations": {"expected_response": "Organization"}
    },
    {
        "inputs": {"request": "What is the purpose of ROUGE (Recall-Oriented Understudy for Gisting Evaluation) in automatic evaluation methods?"},
        "expectations": {"expected_response": "ROUGE (Recall-Oriented Understudy for Gisting Evaluation) is used in automatic evaluation methods to evaluate the quality of machine translation. It calculates N-gram co-occurrence statistics, which are used to assess the similarity between the candidate text and the reference text. ROUGE is based on recall, whereas BLEU is based on accuracy."}
    },
    {
        "inputs": {"request": "What are the challenges associated with Foundation SSL in CV, and how do they relate to the lack of theoretical foundation, semantic understanding, and explicable exploration?"},
        "expectations": {"expected_response": "The challenges associated with Foundation SSL in CV include the lack of a profound theory to support all kinds of tentative experiments, and further exploration has no handbook. The pretrained LM may not learn the meaning of the language, relying on corpus learning instead. The models cannot reach a better level of stability and match different downstream tasks, and the primary method is to increase data, improve computation power, and design training procedures to achieve better results. The lack of theoretical foundation, semantic understanding, and explicable exploration are the main challenges in Foundation SSL in CV."}
    },
    {
        "inputs": {"request": "How does ChatGPT handle factual input compared to GPT-3.5?"},
        "expectations": {"expected_response": "ChatGPT handles factual input better than GPT-3.5, with a 21.9% increase in accuracy when the premise entails the hypothesis. This is possibly related to the preference for human feedback in ChatGPT's RLHF design during model training."}
    },
    {
        "inputs": {"request": "What are some of the challenges in understanding natural language commands for robotic navigation and mobile manipulation?"},
        "expectations": {"expected_response": "Some challenges in understanding natural language commands for robotic navigation and mobile manipulation include integrating natural language understanding with reinforcement learning, understanding natural language directions for robotic navigation, and mapping instructions and visual observations to actions with reinforcement learning."}
    },
    {
        "inputs": {"request": "How does chain of thought prompting elicit reasoning in large language models, and what are the potential applications of this technique in neural text generation and human-AI interaction?"},
        "expectations": {"expected_response": "The context discusses the use of chain of thought prompting to elicit reasoning in large language models, which can be applied in neural text generation and human-AI interaction. Specifically, researchers have used this technique to train language models to generate coherent and contextually relevant text, and to create transparent and controllable human-AI interaction systems. The potential applications of this technique include improving the performance of language models in generating contextually appropriate responses, enhancing the interpretability and controllability of AI systems, and facilitating more effective human-AI collaboration."}
    },
    {
        "inputs": {"request": "Using the given context, how can the robot be instructed to move objects around on a tabletop to complete rearrangement tasks?"},
        "expectations": {"expected_response": "The robot can be instructed to move objects around on a tabletop to complete rearrangement tasks by using natural language instructions that specify the objects to be moved and their desired locations. The instructions can be parsed using functions such as parse_obj_name and parse_position to extract the necessary information, and then passed to a motion primitive that can pick up and place objects in the specified locations. The get_obj_names and get_obj_pos APIs can be used to access information about the available objects and their locations in the scene."}
    },
    {
        "inputs": {"request": "How can searching over an organization's existing knowledge, data, or documents using LLM-powered applications reduce the time it takes to complete worker activities?"},
        "expectations": {"expected_response": "Using AI tools to search through a company's information can significantly cut down the time workers need to finish tasks. These tools quickly find and provide the necessary details by scanning large amounts of data efficiently."}
    }
]

print(f"Created eval_dataset with {len(DA.eval_dataset)} evaluation items")